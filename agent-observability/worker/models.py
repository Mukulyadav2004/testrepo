"""SQLAlchemy models for persisted traces, span events, and evaluations."""
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
from sqlalchemy.types import JSON

Base = declarative_base()


class Trace(Base):
    __tablename__ = "traces"

    trace_id = Column(String, primary_key=True)
    session_id = Column(String)
    app_name = Column(String)
    input = Column(String)
    output = Column(String)
    model_name = Column(String)
    latency_ms = Column(Float)
    token_count = Column(Integer)
    timestamp = Column(BigInteger)
    created_at = Column(DateTime, default=datetime.utcnow)


class SpanEvent(Base):
    __tablename__ = "span_events"

    span_id = Column(String, primary_key=True)
    trace_id = Column(String, ForeignKey("traces.trace_id"))
    event_type = Column(String)
    timestamp = Column(BigInteger)
    # `metadata` is reserved on the declarative base, so map the attribute to a
    # differently-named column that still persists as "metadata" in the table.
    event_metadata = Column("metadata", JSON)


class Evaluation(Base):
    __tablename__ = "evaluations"

    eval_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String, ForeignKey("traces.trace_id"))
    score = Column(Float)
    reason = Column(Text)
    evaluator = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


async def init_db(engine):
    """Create all tables. Expects an AsyncEngine."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
