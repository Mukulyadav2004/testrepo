"""REST API server exposing traces, span events, and evaluation results.

Reads from PostgreSQL via asyncpg and can trigger the Lambda evaluator inline.
"""
import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

# The evaluator lives in a sibling service dir; make it importable so the
# /evaluate endpoint can call the Lambda handler inline.
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "evaluator"))
)
from handler import lambda_handler  # noqa: E402

# asyncpg wants a plain DSN, so strip any SQLAlchemy async driver suffix.
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://agentobs:agentobs@localhost:5432/agentobs"
).replace("+asyncpg", "")


# --------------------------------------------------------------------------- #
# Pydantic response models
# --------------------------------------------------------------------------- #
class TraceSummary(BaseModel):
    trace_id: str
    session_id: Optional[str] = None
    app_name: Optional[str] = None
    input: Optional[str] = None
    output: Optional[str] = None
    model_name: Optional[str] = None
    latency_ms: Optional[float] = None
    token_count: Optional[int] = None
    timestamp: Optional[int] = None


class SpanEventModel(BaseModel):
    span_id: str
    trace_id: Optional[str] = None
    event_type: Optional[str] = None
    timestamp: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class TraceDetail(TraceSummary):
    span_events: List[SpanEventModel] = []


class EvaluationModel(BaseModel):
    eval_id: str
    trace_id: Optional[str] = None
    score: Optional[float] = None
    reason: Optional[str] = None
    evaluator: Optional[str] = None


class ModelCount(BaseModel):
    model_name: Optional[str] = None
    count: int


class StatsModel(BaseModel):
    total_traces: int
    avg_latency_ms: Optional[float] = None
    avg_score: Optional[float] = None
    traces_per_model: List[ModelCount] = []


class EvaluateResponse(BaseModel):
    statusCode: int
    score: Optional[float] = None
    reason: Optional[str] = None
    error: Optional[str] = None


# --------------------------------------------------------------------------- #
# App + connection pool lifecycle
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await asyncpg.create_pool(dsn=DATABASE_URL)
    try:
        yield
    finally:
        await app.state.pool.close()


app = FastAPI(title="Agent Observability API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_pool() -> asyncpg.Pool:
    return app.state.pool


def _parse_metadata(value: Any) -> Optional[Dict[str, Any]]:
    """asyncpg returns JSON columns as strings; decode to a dict when possible."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@app.get("/traces", response_model=List[TraceSummary])
async def list_traces(
    app_name: Optional[str] = None,
    model_name: Optional[str] = None,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
):
    conditions = []
    params: List[Any] = []
    if app_name is not None:
        params.append(app_name)
        conditions.append(f"app_name = ${len(params)}")
    if model_name is not None:
        params.append(model_name)
        conditions.append(f"model_name = ${len(params)}")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)
    limit_idx = len(params)
    params.append(offset)
    offset_idx = len(params)

    query = (
        "SELECT trace_id, session_id, app_name, input, output, model_name, "
        "latency_ms, token_count, timestamp FROM traces "
        f"{where} ORDER BY timestamp DESC NULLS LAST "
        f"LIMIT ${limit_idx} OFFSET ${offset_idx}"
    )
    rows = await pool.fetch(query, *params)
    return [TraceSummary(**dict(row)) for row in rows]


@app.get("/traces/{trace_id}", response_model=TraceDetail)
async def get_trace(trace_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    trace_row = await pool.fetchrow(
        "SELECT trace_id, session_id, app_name, input, output, model_name, "
        "latency_ms, token_count, timestamp FROM traces WHERE trace_id = $1",
        trace_id,
    )
    if trace_row is None:
        raise HTTPException(status_code=404, detail="trace not found")

    span_rows = await pool.fetch(
        'SELECT span_id, trace_id, event_type, timestamp, metadata '
        "FROM span_events WHERE trace_id = $1",
        trace_id,
    )
    spans = [
        SpanEventModel(
            span_id=row["span_id"],
            trace_id=row["trace_id"],
            event_type=row["event_type"],
            timestamp=row["timestamp"],
            metadata=_parse_metadata(row["metadata"]),
        )
        for row in span_rows
    ]
    return TraceDetail(**dict(trace_row), span_events=spans)


@app.get("/traces/{trace_id}/evaluation", response_model=EvaluationModel)
async def get_evaluation(trace_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    row = await pool.fetchrow(
        "SELECT eval_id, trace_id, score, reason, evaluator FROM evaluations "
        "WHERE trace_id = $1 ORDER BY created_at DESC LIMIT 1",
        trace_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="evaluation not found")
    data = dict(row)
    data["eval_id"] = str(data["eval_id"])
    return EvaluationModel(**data)


@app.post("/traces/{trace_id}/evaluate", response_model=EvaluateResponse)
async def evaluate_trace(trace_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    trace_row = await pool.fetchrow(
        "SELECT trace_id, input, output FROM traces WHERE trace_id = $1", trace_id
    )
    if trace_row is None:
        raise HTTPException(status_code=404, detail="trace not found")

    event = {
        "trace_id": trace_row["trace_id"],
        "input": trace_row["input"],
        "output": trace_row["output"],
    }
    # lambda_handler is synchronous (httpx + psycopg2); run off the event loop.
    result = await run_in_threadpool(lambda_handler, event, None)
    return EvaluateResponse(**result)


@app.get("/stats", response_model=StatsModel)
async def get_stats(pool: asyncpg.Pool = Depends(get_pool)):
    agg = await pool.fetchrow(
        "SELECT COUNT(*) AS total_traces, AVG(latency_ms) AS avg_latency_ms FROM traces"
    )
    avg_score = await pool.fetchval("SELECT AVG(score) FROM evaluations")
    model_rows = await pool.fetch(
        "SELECT model_name, COUNT(*) AS count FROM traces "
        "GROUP BY model_name ORDER BY count DESC"
    )
    return StatsModel(
        total_traces=agg["total_traces"],
        avg_latency_ms=agg["avg_latency_ms"],
        avg_score=avg_score,
        traces_per_model=[ModelCount(**dict(r)) for r in model_rows],
    )
