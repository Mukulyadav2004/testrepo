"""Async gRPC ingestion server.

Receives traces from the SDK, validates them, and pushes each trace (plus its span
events) as a JSON payload onto the Redis Stream named ``traces``.
"""
import asyncio
import json
import logging
import os

import grpc
import redis.asyncio as redis
from google.protobuf.json_format import MessageToDict

import trace_pb2
import trace_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("ingestion-server")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
GRPC_PORT = 50051
STREAM_NAME = "traces"


class TraceIngestionService(trace_pb2_grpc.TraceIngestionServiceServicer):
    """Implements the TraceIngestionService RPCs."""

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    async def IngestTrace(self, request, context):
        trace = request.trace

        # --- Validation ---
        missing = [
            name
            for name, value in (
                ("trace_id", trace.trace_id),
                ("input", trace.input),
                ("output", trace.output),
            )
            if not value
        ]
        if missing:
            message = f"validation failed: missing or empty field(s): {', '.join(missing)}"
            logger.warning("%s (trace_id=%r)", message, trace.trace_id)
            return trace_pb2.IngestTraceResponse(success=False, message=message)

        # --- Serialize to a JSON payload ---
        payload = {
            "trace": MessageToDict(trace, preserving_proto_field_name=True),
            "span_events": [
                MessageToDict(span, preserving_proto_field_name=True)
                for span in request.span_events
            ],
        }
        data = json.dumps(payload)

        # --- Push to Redis Stream ---
        try:
            await self._redis.xadd(STREAM_NAME, {"data": data})
        except (redis.RedisError, OSError) as exc:
            message = f"failed to push trace to redis: {exc}"
            logger.error("%s (trace_id=%s)", message, trace.trace_id)
            return trace_pb2.IngestTraceResponse(success=False, message=message)

        logger.info("ingested trace_id=%s", trace.trace_id)
        return trace_pb2.IngestTraceResponse(success=True, message="trace ingested")


async def serve():
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    server = grpc.aio.server()
    trace_pb2_grpc.add_TraceIngestionServiceServicer_to_server(
        TraceIngestionService(redis_client), server
    )
    listen_addr = f"[::]:{GRPC_PORT}"
    server.add_insecure_port(listen_addr)

    logger.info("starting gRPC ingestion server on %s", listen_addr)
    logger.info("redis target %s:%s, stream=%s", REDIS_HOST, REDIS_PORT, STREAM_NAME)
    await server.start()
    try:
        await server.wait_for_termination()
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(serve())
