"""Redis Streams worker.

Consumes trace payloads from the Redis Stream ``traces`` via a consumer group and
persists them (the trace plus its span events) into PostgreSQL.
"""
import asyncio
import json
import logging
import os

import redis.asyncio as redis
from redis.exceptions import ResponseError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models import SpanEvent, Trace, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("worker")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://agentobs:agentobs@localhost:5432/agentobs"
)

STREAM_NAME = "traces"
GROUP_NAME = "workers"
CONSUMER_NAME = "worker-1"


async def ensure_group(redis_client):
    """Create the consumer group, tolerating the case where it already exists."""
    try:
        await redis_client.xgroup_create(
            name=STREAM_NAME, groupname=GROUP_NAME, id="0", mkstream=True
        )
        logger.info("created consumer group %s on stream %s", GROUP_NAME, STREAM_NAME)
    except ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            logger.info("consumer group %s already exists", GROUP_NAME)
        else:
            raise


async def store_trace(session_factory, payload):
    """Insert a trace and its span events. Returns False if it was a duplicate."""
    trace_data = payload.get("trace", {})
    span_events = payload.get("span_events", [])
    trace_id = trace_data.get("trace_id")

    async with session_factory() as session:
        try:
            raw_ts = trace_data.get("timestamp")
            raw_tc = trace_data.get("token_count")
            raw_lat = trace_data.get("latency_ms")
            session.add(
                Trace(
                    trace_id=trace_id,
                    session_id=trace_data.get("session_id"),
                    app_name=trace_data.get("app_name"),
                    input=trace_data.get("input"),
                    output=trace_data.get("output"),
                    model_name=trace_data.get("model_name"),
                    latency_ms=float(raw_lat) if raw_lat is not None else None,
                    token_count=int(raw_tc) if raw_tc is not None else None,
                    timestamp=int(raw_ts) if raw_ts is not None else None,
                )
            )
            for span in span_events:
                raw_span_ts = span.get("timestamp")
                session.add(
                    SpanEvent(
                        span_id=span.get("span_id"),
                        trace_id=span.get("trace_id"),
                        event_type=span.get("event_type"),
                        timestamp=int(raw_span_ts) if raw_span_ts is not None else None,
                        event_metadata=span.get("metadata"),
                    )
                )
            await session.commit()
        except IntegrityError:
            await session.rollback()
            logger.info("duplicate trace_id=%s, skipping", trace_id)
            return False

    logger.info(
        "stored trace_id=%s with %d span event(s)", trace_id, len(span_events)
    )
    return True


async def process_message(redis_client, session_factory, message_id, fields):
    """Parse a single stream message, persist it, and acknowledge it."""
    try:
        payload = json.loads(fields["data"])
    except (KeyError, json.JSONDecodeError) as exc:
        logger.error("failed to parse message %s: %s; acking to discard", message_id, exc)
        await redis_client.xack(STREAM_NAME, GROUP_NAME, message_id)
        return

    await store_trace(session_factory, payload)
    await redis_client.xack(STREAM_NAME, GROUP_NAME, message_id)
    logger.info("acked message %s", message_id)


async def run():
    redis_client = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
    )
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    await init_db(engine)
    await ensure_group(redis_client)

    logger.info(
        "worker %s started, consuming stream=%s group=%s",
        CONSUMER_NAME,
        STREAM_NAME,
        GROUP_NAME,
    )

    try:
        while True:
            response = await redis_client.xreadgroup(
                groupname=GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={STREAM_NAME: ">"},
                count=10,
            )
            for _stream, messages in response or []:
                for message_id, fields in messages:
                    await process_message(
                        redis_client, session_factory, message_id, fields
                    )
            await asyncio.sleep(0.1)
    finally:
        await redis_client.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
