"""
Benchmark suite for the Agent Observability & Evaluation Platform.

Usage (from repo root):
    python3 benchmark/load_test.py

All connection details are read from environment variables:
    GRPC_HOST       gRPC ingestion server host (default: localhost)
    GRPC_PORT       gRPC ingestion server port (default: 50051)
    REDIS_HOST      Redis host (default: localhost)
    REDIS_PORT      Redis port (default: 6379)
    DATABASE_URL    asyncpg DSN  (default: postgresql://agentobs:agentobs@localhost:5432/agentobs)
    API_BASE_URL    REST API base (default: http://localhost:8000)
"""

import asyncio
import os
import statistics
import sys
import time
import uuid

# ── gRPC stubs live in ingestion-server/ ──────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion-server"))

import asyncpg
import grpc
import httpx
import redis.asyncio as redis

import trace_pb2
import trace_pb2_grpc

# ── connection config ──────────────────────────────────────────────────────────
GRPC_HOST = os.getenv("GRPC_HOST", "localhost")
GRPC_PORT = int(os.getenv("GRPC_PORT", "50051"))
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
DATABASE_URL = (
    os.getenv("DATABASE_URL", "postgresql://agentobs:agentobs@localhost:5432/agentobs")
    .replace("+asyncpg", "")
    .replace("+psycopg2", "")
)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


# ── helpers ────────────────────────────────────────────────────────────────────

def _now_ms() -> int:
    return int(time.time() * 1000)


def _make_request(trace_id: str, model: str = "gpt-4") -> trace_pb2.IngestTraceRequest:
    return trace_pb2.IngestTraceRequest(
        trace=trace_pb2.Trace(
            trace_id=trace_id,
            session_id=str(uuid.uuid4()),
            app_name="benchmark",
            timestamp=_now_ms(),
            input="What is agent observability?",
            output="Agent observability is the practice of instrumenting AI agents.",
            latency_ms=42.0,
            model_name=model,
            token_count=32,
        ),
        span_events=[],
    )


def _percentile(sorted_data: list, p: float) -> float:
    if not sorted_data:
        return 0.0
    idx = int(len(sorted_data) * p / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]


# ── benchmark 1: gRPC ingestion throughput ────────────────────────────────────

async def bench_grpc_throughput(n: int = 1000) -> float:
    """Send n traces concurrently; return traces/second."""
    channel = grpc.aio.insecure_channel(f"{GRPC_HOST}:{GRPC_PORT}")
    stub = trace_pb2_grpc.TraceIngestionServiceStub(channel)

    async def send_one():
        req = _make_request(str(uuid.uuid4()))
        await stub.IngestTrace(req)

    start = time.perf_counter()
    await asyncio.gather(*[send_one() for _ in range(n)])
    elapsed = time.perf_counter() - start
    await channel.close()
    return n / elapsed


# ── benchmark 2: end-to-end latency (send → visible in Postgres) ──────────────

async def bench_e2e_latency(n: int = 50) -> tuple[float, float, float]:
    """Measure trace_id appearing in the traces table. Returns (p50, p95, p99) ms."""
    channel = grpc.aio.insecure_channel(f"{GRPC_HOST}:{GRPC_PORT}")
    stub = trace_pb2_grpc.TraceIngestionServiceStub(channel)
    pool = await asyncpg.create_pool(dsn=DATABASE_URL)

    async def measure_one() -> float:
        trace_id = str(uuid.uuid4())
        req = _make_request(trace_id)
        t0 = time.perf_counter()
        await stub.IngestTrace(req)
        # Poll until the worker writes to PostgreSQL (max 5 s).
        for _ in range(500):
            row = await pool.fetchval(
                "SELECT trace_id FROM traces WHERE trace_id = $1", trace_id
            )
            if row:
                return (time.perf_counter() - t0) * 1000
            await asyncio.sleep(0.01)
        return 5000.0  # timeout sentinel

    # Run sequentially to get clean per-trace timings without queue confusion.
    latencies = []
    for _ in range(n):
        ms = await measure_one()
        latencies.append(ms)

    await channel.close()
    await pool.close()

    latencies.sort()
    return (
        _percentile(latencies, 50),
        _percentile(latencies, 95),
        _percentile(latencies, 99),
    )


# ── benchmark 3: Redis stream backlog under burst ─────────────────────────────

async def bench_redis_backlog(n: int = 500) -> int:
    """Send n traces as fast as possible, then sample the pending count."""
    channel = grpc.aio.insecure_channel(f"{GRPC_HOST}:{GRPC_PORT}")
    stub = trace_pb2_grpc.TraceIngestionServiceStub(channel)

    async def send_one():
        await stub.IngestTrace(_make_request(str(uuid.uuid4())))

    await asyncio.gather(*[send_one() for _ in range(n)])
    await channel.close()

    # Read the stream length immediately after the burst — before the worker drains it.
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    length = await r.xlen("traces")
    await r.aclose()
    return int(length)


# ── benchmark 4: API response time ───────────────────────────────────────────

async def bench_api_latency(n: int = 200) -> tuple[float, float]:
    """Hit GET /traces n times sequentially. Returns (p50, p95) ms."""
    latencies = []
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0) as client:
        for _ in range(n):
            t0 = time.perf_counter()
            await client.get("/traces")
            latencies.append((time.perf_counter() - t0) * 1000)
    latencies.sort()
    return _percentile(latencies, 50), _percentile(latencies, 95)


# ── main ───────────────────────────────────────────────────────────────────────

def _fmt(value: float, unit: str = "") -> str:
    return f"{value:>10.1f}{unit}"


async def main():
    print("Starting benchmark suite…\n")

    print("[1/4] gRPC throughput (1 000 concurrent traces)…")
    throughput = await bench_grpc_throughput(1000)

    print("[2/4] End-to-end latency (50 traces, polling Postgres)…")
    p50_e2e, p95_e2e, p99_e2e = await bench_e2e_latency(50)

    print("[3/4] Redis backlog under burst (500 traces)…")
    backlog = await bench_redis_backlog(500)

    print("[4/4] API response time (200 × GET /traces)…")
    p50_api, p95_api = await bench_api_latency(200)

    print()
    print("=" * 52)
    print("             Benchmark Results")
    print("=" * 52)
    print(f"  gRPC ingestion throughput:   {_fmt(throughput)} traces/sec")
    print(f"  End-to-end latency p50:      {_fmt(p50_e2e)} ms")
    print(f"  End-to-end latency p95:      {_fmt(p95_e2e)} ms")
    print(f"  End-to-end latency p99:      {_fmt(p99_e2e)} ms")
    print(f"  Redis max backlog (500 msg): {backlog:>11} messages")
    print(f"  API GET /traces p50:         {_fmt(p50_api)} ms")
    print(f"  API GET /traces p95:         {_fmt(p95_api)} ms")
    print("=" * 52)


if __name__ == "__main__":
    asyncio.run(main())
