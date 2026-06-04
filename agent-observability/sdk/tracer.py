"""Python SDK for instrumenting an AI app and shipping traces to the ingestion server."""
import functools
import json
import logging
import time
import uuid

import grpc

import trace_pb2
import trace_pb2_grpc

logger = logging.getLogger("agent-tracer")


def _now_ms() -> int:
    """Current wall-clock time as Unix epoch milliseconds."""
    return int(time.time() * 1000)


def _stringify(value) -> str:
    """Best-effort string representation for capturing function input/output."""
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)


class AgentTracer:
    """Client that sends traces to the gRPC ingestion server."""

    def __init__(self, app_name, server_host="localhost", server_port=50051):
        self.app_name = app_name
        self._target = f"{server_host}:{server_port}"
        self._channel = grpc.aio.insecure_channel(self._target)
        self._stub = trace_pb2_grpc.TraceIngestionServiceStub(self._channel)

    async def trace(
        self,
        trace_id,
        session_id,
        input,
        output,
        model_name,
        latency_ms,
        token_count,
        span_events=None,
    ):
        """Build an IngestTraceRequest and send it to the ingestion server."""
        span_events = span_events or []

        trace_msg = trace_pb2.Trace(
            trace_id=trace_id,
            session_id=session_id,
            app_name=self.app_name,
            timestamp=_now_ms(),
            input=input,
            output=output,
            latency_ms=latency_ms,
            model_name=model_name,
            token_count=token_count,
        )

        request = trace_pb2.IngestTraceRequest(
            trace=trace_msg,
            span_events=span_events,
        )

        response = await self._stub.IngestTrace(request)
        if not response.success:
            logger.warning(
                "trace %s rejected by ingestion server: %s",
                trace_id,
                response.message,
            )
        return response

    def instrument(self, func):
        """Decorator that wraps an async function, auto-capturing input/output/latency.

        Usage::

            @tracer.instrument
            async def call_llm(prompt): ...
        """

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            captured_input = _stringify({"args": args, "kwargs": kwargs})
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            latency_ms = (time.perf_counter() - start) * 1000.0

            captured_output = _stringify(result)
            await self.trace(
                trace_id=str(uuid.uuid4()),
                session_id=str(uuid.uuid4()),
                input=captured_input,
                output=captured_output,
                model_name="unknown",
                latency_ms=latency_ms,
                token_count=0,
            )
            return result

        return wrapper

    async def close(self):
        """Close the underlying gRPC channel."""
        await self._channel.close()
