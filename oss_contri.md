"""
Layer 1: Rule-based failure classifier.

Sentry-style fast detection — deterministic, cheap, runs before any LLM call.
Catches ~35-40% of real production failures instantly.

Design principle: every rule returns a result with a confidence.
Hard rules (explicit error codes) → confidence 0.95
Soft rules (heuristics, thresholds) → confidence 0.70-0.85
Multiple soft rules agreeing → combined confidence up to 0.90
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Callable
import statistics

from openweave.classifier.models.trace import (
    NormalizedTrace, TraceStep, StepType,
    FailureType, ClassifierOutput
)


# ── Rule result ─────────────────────────────────────────────────────────────

@dataclass
class RuleMatch:
    failure_type: FailureType
    confidence:   float
    evidence:     list[str]   # step_ids
    reason:       str
    rule_name:    str


# ── Individual rules ─────────────────────────────────────────────────────────

def rule_tool_http_error(trace: NormalizedTrace) -> Optional[RuleMatch]:
    """
    Tool call returned 4xx/5xx HTTP status.
    Hard rule — status code is deterministic evidence.
    Sentry equivalent: exception type matching.
    """
    for step in trace.tool_steps():
        if step.error and step.error.status_code:
            code = step.error.status_code
            if 400 <= code <= 499:
                return RuleMatch(
                    failure_type=FailureType.TOOL,
                    confidence=0.95,
                    evidence=[step.step_id],
                    reason=f"Tool '{step.tool_name}' returned HTTP {code} (client error).",
                    rule_name="tool_http_4xx",
                )
            if 500 <= code <= 599:
                return RuleMatch(
                    failure_type=FailureType.INFRA,
                    confidence=0.90,
                    evidence=[step.step_id],
                    reason=f"Tool '{step.tool_name}' returned HTTP {code} (server error — likely infra).",
                    rule_name="tool_http_5xx",
                )
    return None


def rule_output_parsing_failure(trace: NormalizedTrace) -> Optional[RuleMatch]:
    """
    Final output step failed to parse expected format (JSON, XML, structured).
    Hard rule — parse errors are deterministic.
    """
    output_steps = [s for s in trace.steps if s.step_type == StepType.OUTPUT]
    for step in output_steps:
        if step.error and step.error.type in (
            "JSONDecodeError", "ParseError", "ValidationError",
            "OutputParserException", "json.decoder.JSONDecodeError"
        ):
            return RuleMatch(
                failure_type=FailureType.PARSING,
                confidence=0.95,
                evidence=[step.step_id],
                reason="Output parsing failed — LLM returned malformed structured output.",
                rule_name="output_parsing_error",
            )
    return None


def rule_timeout(trace: NormalizedTrace) -> Optional[RuleMatch]:
    """
    Any step exceeded latency threshold with no error code.
    Soft rule — high latency is a signal, not proof.
    """
    # Compute baseline from non-error steps of same type
    llm_latencies = [
        s.latency_ms for s in trace.steps
        if s.step_type == StepType.LLM_CALL and not s.error
    ]
    threshold = 8000  # ms — hard floor
    dynamic_threshold = None
    if len(llm_latencies) >= 3:
        mean = statistics.mean(llm_latencies)
        stdev = statistics.stdev(llm_latencies)
        dynamic_threshold = mean + (2.5 * stdev)

    for step in trace.steps:
        effective_threshold = dynamic_threshold or threshold
        if step.latency_ms > effective_threshold and not step.error:
            return RuleMatch(
                failure_type=FailureType.INFRA,
                confidence=0.75,
                evidence=[step.step_id],
                reason=f"Step '{step.step_id}' timed out ({step.latency_ms:.0f}ms, "
                       f"threshold {effective_threshold:.0f}ms) with no error — infra or rate-limit.",
                rule_name="latency_timeout",
            )
    return None


def rule_low_retrieval_similarity(trace: NormalizedTrace) -> Optional[RuleMatch]:
    """
    Retrieval step returned low similarity scores.
    Soft rule — similarity < 0.35 is a strong signal of retrieval failure.
    This is where we start diverging from Sentry (no equivalent in traditional APM).
    """
    bad_retrievals = [
        s for s in trace.retrieval_steps()
        if s.similarity_score is not None and s.similarity_score < 0.35
    ]
    if bad_retrievals:
        evidence = [s.step_id for s in bad_retrievals]
        worst = min(bad_retrievals, key=lambda s: s.similarity_score)
        return RuleMatch(
            failure_type=FailureType.RETRIEVAL,
            confidence=0.82,
            evidence=evidence,
            reason=f"Retrieval returned low-similarity chunks "
                   f"(worst: {worst.similarity_score:.2f}). "
                   f"Context fed to LLM is likely irrelevant.",
            rule_name="low_retrieval_similarity",
        )
    return None


def rule_empty_retrieval(trace: NormalizedTrace) -> Optional[RuleMatch]:
    """
    Retrieval step returned zero results.
    Hard rule — empty retrieval is always a failure.
    """
    for step in trace.retrieval_steps():
        output = step.output or {}
        results = output.get("results") or output.get("documents") or output.get("chunks") or []
        if isinstance(results, list) and len(results) == 0:
            return RuleMatch(
                failure_type=FailureType.RETRIEVAL,
                confidence=0.92,
                evidence=[step.step_id],
                reason="Retrieval returned zero results — query produced no matching chunks.",
                rule_name="empty_retrieval",
            )
    return None


def rule_tool_not_found(trace: NormalizedTrace) -> Optional[RuleMatch]:
    """
    Agent called a tool that doesn't exist or isn't registered.
    Hard rule — tool_not_found errors are deterministic.
    """
    for step in trace.tool_steps():
        if step.error and step.error.type in (
            "ToolNotFoundException", "UnknownToolError",
            "tool_not_found", "AttributeError"
        ):
            return RuleMatch(
                failure_type=FailureType.TOOL,
                confidence=0.93,
                evidence=[step.step_id],
                reason=f"Tool '{step.tool_name}' not found — routing logic selected an unregistered tool.",
                rule_name="tool_not_found",
            )
    return None


def rule_memory_read_failure(trace: NormalizedTrace) -> Optional[RuleMatch]:
    """
    Memory read step failed or returned empty when history expected.
    Soft rule.
    """
    memory_steps = [s for s in trace.steps if s.step_type == StepType.MEMORY]
    for step in memory_steps:
        if step.error:
            return RuleMatch(
                failure_type=FailureType.MEMORY,
                confidence=0.85,
                evidence=[step.step_id],
                reason=f"Memory read failed: {step.error.message}",
                rule_name="memory_read_error",
            )
        output = step.output or {}
        history = output.get("history") or output.get("messages") or []
        if isinstance(history, list) and len(history) == 0:
            return RuleMatch(
                failure_type=FailureType.MEMORY,
                confidence=0.65,
                evidence=[step.step_id],
                reason="Memory read returned empty history — context may be lost.",
                rule_name="empty_memory",
            )
    return None


def rule_model_rate_limit(trace: NormalizedTrace) -> Optional[RuleMatch]:
    """
    LLM API returned rate limit error (429).
    Hard rule.
    """
    for step in trace.steps:
        if step.step_type == StepType.LLM_CALL:
            if step.error and step.error.status_code == 429:
                return RuleMatch(
                    failure_type=FailureType.MODEL,
                    confidence=0.97,
                    evidence=[step.step_id],
                    reason=f"Model '{step.model_name}' rate-limited (HTTP 429). "
                           f"Requests exceed API quota.",
                    rule_name="model_rate_limit",
                )
    return None


def rule_context_overflow(trace: NormalizedTrace) -> Optional[RuleMatch]:
    """
    LLM call exceeded context window limit.
    Hard rule — context length errors are deterministic.
    """
    overflow_keywords = [
        "maximum context length", "context_length_exceeded",
        "token limit", "max_tokens", "context window"
    ]
    for step in trace.steps:
        if step.step_type == StepType.LLM_CALL and step.error:
            msg = (step.error.message or "").lower()
            if any(kw in msg for kw in overflow_keywords):
                return RuleMatch(
                    failure_type=FailureType.MODEL,
                    confidence=0.96,
                    evidence=[step.step_id],
                    reason="LLM call exceeded context window — too many tokens sent to model.",
                    rule_name="context_overflow",
                )
    return None


# ── Rule registry ─────────────────────────────────────────────────────────────

RULES: list[Callable[[NormalizedTrace], Optional[RuleMatch]]] = [
    # Hard rules first (highest confidence, most deterministic)
    rule_tool_http_error,
    rule_output_parsing_failure,
    rule_model_rate_limit,
    rule_context_overflow,
    rule_tool_not_found,
    rule_empty_retrieval,
    # Soft rules second
    rule_low_retrieval_similarity,
    rule_memory_read_failure,
    rule_timeout,
]


# ── Layer 1 classifier ────────────────────────────────────────────────────────

class RuleBasedClassifier:
    """
    Runs all rules in priority order.
    First match wins for hard rules.
    Soft rules accumulate and can combine confidence.
    Returns None if no rule fires → escalate to LLM layer.
    """

    HARD_RULES = {
        "tool_http_4xx", "tool_http_5xx", "output_parsing_error",
        "model_rate_limit", "context_overflow", "tool_not_found",
        "empty_retrieval",
    }

    def classify(self, trace: NormalizedTrace) -> Optional[ClassifierOutput]:
        matches: list[RuleMatch] = []

        for rule_fn in RULES:
            match = rule_fn(trace)
            if match:
                # Hard rule → return immediately, no ambiguity
                if match.rule_name in self.HARD_RULES:
                    return ClassifierOutput(
                        failure_type=match.failure_type,
                        confidence=match.confidence,
                        evidence=match.evidence,
                        reason=match.reason,
                        layer="rule_based",
                        fingerprint=trace.fingerprint(),
                    )
                matches.append(match)

        if not matches:
            return None  # No rule fired → escalate to LLM

        # Multiple soft rules: pick highest confidence match
        # If two different failure types both fire, flag secondary suspect
        primary = max(matches, key=lambda m: m.confidence)
        others  = [m for m in matches if m.failure_type != primary.failure_type]
        secondary = max(others, key=lambda m: m.confidence).failure_type if others else None

        # Boost confidence if multiple rules agree on same failure type
        agreeing = [m for m in matches if m.failure_type == primary.failure_type]
        boosted_confidence = min(0.92, primary.confidence + (0.04 * (len(agreeing) - 1)))

        all_evidence = list({step for m in agreeing for step in m.evidence})

        return ClassifierOutput(
            failure_type=primary.failure_type,
            confidence=boosted_confidence,
            evidence=all_evidence,
            reason=primary.reason,
            secondary_suspect=secondary,
            layer="rule_based",
            fingerprint=trace.fingerprint(),
        )
