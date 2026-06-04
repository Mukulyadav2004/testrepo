"""AWS Lambda-style LLM-as-judge evaluator backed by Ollama.

Given a trace's input/output, asks an Ollama-hosted model to score the output on
relevance, correctness, and conciseness, then records the result in PostgreSQL.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import httpx
import psycopg2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("evaluator")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
PRIMARY_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
FALLBACK_MODEL = os.getenv("OLLAMA_FALLBACK_MODEL", "mistral")
# psycopg2 needs a plain libpq DSN, so drop any SQLAlchemy async/sync driver suffix
# (lets this share the same DATABASE_URL secret the worker uses with +asyncpg).
DATABASE_URL = (
    os.getenv("DATABASE_URL", "postgresql://agentobs:agentobs@localhost:5432/agentobs")
    .replace("+asyncpg", "")
    .replace("+psycopg2", "")
)
REQUEST_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "60"))

PROMPT_TEMPLATE = """You are an impartial evaluator (LLM-as-judge). Evaluate the \
ASSISTANT OUTPUT given the USER INPUT on three criteria:
- relevance: does the output address the input?
- correctness: is the output accurate?
- conciseness: is the output appropriately succinct?

Respond with ONLY a JSON object of the form:
{{"score": <float between 0.0 and 1.0>, "reason": "<one or two sentence explanation>"}}

USER INPUT:
{input}

ASSISTANT OUTPUT:
{output}
"""


def _call_ollama(model: str, prompt: str) -> dict:
    """Call the Ollama generate API with JSON formatting and return the parsed verdict."""
    resp = httpx.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    # Ollama wraps the model's output in a "response" string field.
    raw = resp.json().get("response", "")
    return json.loads(raw)


def evaluate(input_text: str, output_text: str):
    """Run the judge, trying the primary model then falling back to the secondary.

    Returns a tuple ``(model_used, score, reason)``.
    """
    prompt = PROMPT_TEMPLATE.format(input=input_text, output=output_text)
    last_error = None
    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        try:
            verdict = _call_ollama(model, prompt)
            score = float(verdict["score"])
            reason = str(verdict.get("reason", ""))
            return model, score, reason
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("evaluation with model %s failed: %s", model, exc)
            last_error = exc
    raise RuntimeError(f"all models failed; last error: {last_error}")


def _store_evaluation(trace_id: str, score: float, reason: str, evaluator: str) -> None:
    """Insert the evaluation result into the PostgreSQL evaluations table."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO evaluations
                    (eval_id, trace_id, score, reason, evaluator, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    trace_id,
                    score,
                    reason,
                    evaluator,
                    datetime.now(timezone.utc),
                ),
            )
    finally:
        conn.close()


def lambda_handler(event, context):
    """Lambda entry point. Expects event with trace_id, input, output."""
    trace_id = event.get("trace_id")
    input_text = event.get("input", "")
    output_text = event.get("output", "")
    logger.info("evaluating trace_id=%s", trace_id)

    try:
        model_used, score, reason = evaluate(input_text, output_text)
    except Exception as exc:  # Ollama / parsing failures
        logger.error("evaluation failed for trace_id=%s: %s", trace_id, exc)
        return {"statusCode": 500, "error": f"evaluation failed: {exc}"}

    try:
        _store_evaluation(trace_id, score, reason, evaluator=f"ollama:{model_used}")
    except Exception as exc:  # psycopg2 / DB failures
        logger.error("failed to store evaluation for trace_id=%s: %s", trace_id, exc)
        return {"statusCode": 500, "error": f"db error: {exc}"}

    logger.info("stored evaluation for trace_id=%s score=%s", trace_id, score)
    return {"statusCode": 200, "score": score, "reason": reason}
