"""
OpenWeave Failure Classifier — main orchestrator.

Combines Layer 1 (rule-based) and Layer 2 (LLM) with the confidence gate.
This is the single entry point your API calls.

Usage:
    classifier = FailureClassifier()
    result = classifier.classify(trace)

    if result.is_high_confidence():
        # proceed to context retrieval + fix recommendations
    else:
        # route to guided debug UI
"""
from __future__ import annotations
import time
import logging
from dataclasses import dataclass
from typing import Optional

from openweave.classifier.models.trace import (
    NormalizedTrace, FailureType, ClassifierOutput
)
from openweave.classifier.rules.rule_classifier import RuleBasedClassifier
from openweave.classifier.llm.llm_classifier import LLMClassifier

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Final output from the classifier — what your API returns."""
    output:          ClassifierOutput
    routed_to:       str              # "high_confidence" | "low_confidence"
    classification_ms: float          # time taken
    layer_used:      str              # "rule_based" | "llm" | "combined"

    # Sentry-style deduplication
    fingerprint:     str
    is_duplicate:    bool = False

    def to_dict(self) -> dict:
        return {
            "diagnosis":           self.output.to_dict(),
            "routed_to":           self.routed_to,
            "classification_ms":   round(self.classification_ms, 2),
            "layer_used":          self.layer_used,
            "fingerprint":         self.fingerprint,
            "is_duplicate":        self.is_duplicate,
        }


class FailureClassifier:
    """
    Two-layer failure classifier with confidence gate.

    Layer 1: RuleBasedClassifier — fast, deterministic, free
    Layer 2: LLMClassifier — slower, probabilistic, costs tokens

    Gate: confidence >= threshold → high confidence path
          confidence <  threshold → low confidence path (guided debug)

    Sentry-style fingerprinting for deduplication is applied at every
    classification regardless of which layer produced the result.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.6,
        use_llm_fallback: bool = True,
        seen_fingerprints: Optional[set] = None,
    ):
        self.confidence_threshold = confidence_threshold
        self.use_llm_fallback = use_llm_fallback
        self.rule_classifier = RuleBasedClassifier()
        self.llm_classifier  = LLMClassifier() if use_llm_fallback else None

        # In production, replace with Redis or DB lookup
        self._seen_fingerprints: set[str] = seen_fingerprints or set()

    def classify(self, trace: NormalizedTrace) -> ClassificationResult:
        start = time.perf_counter()

        fingerprint = trace.fingerprint()
        is_duplicate = fingerprint in self._seen_fingerprints
        if not is_duplicate:
            self._seen_fingerprints.add(fingerprint)

        # ── Layer 1: Rule-based ──────────────────────────────────────────────
        rule_result = self.rule_classifier.classify(trace)

        if rule_result is not None:
            logger.info(
                "Rule-based classifier matched: %s (confidence=%.2f, rule=%s)",
                rule_result.failure_type.value, rule_result.confidence, rule_result.layer
            )

            # Rule-based result is already high confidence → skip LLM
            if rule_result.confidence >= self.confidence_threshold:
                elapsed = (time.perf_counter() - start) * 1000
                return ClassificationResult(
                    output=rule_result,
                    routed_to="high_confidence",
                    classification_ms=elapsed,
                    layer_used="rule_based",
                    fingerprint=fingerprint,
                    is_duplicate=is_duplicate,
                )

            # Rule-based matched but confidence is low → run LLM to confirm
            if self.llm_classifier:
                llm_result = self._run_llm(trace)
                combined = self._combine(rule_result, llm_result)
                elapsed = (time.perf_counter() - start) * 1000
                routed = "high_confidence" if combined.confidence >= self.confidence_threshold else "low_confidence"
                return ClassificationResult(
                    output=combined,
                    routed_to=routed,
                    classification_ms=elapsed,
                    layer_used="combined",
                    fingerprint=fingerprint,
                    is_duplicate=is_duplicate,
                )

        # ── Layer 2: LLM fallback ────────────────────────────────────────────
        if self.llm_classifier:
            logger.info("No rule matched — escalating to LLM classifier")
            llm_result = self._run_llm(trace)
            elapsed = (time.perf_counter() - start) * 1000
            routed = "high_confidence" if llm_result.confidence >= self.confidence_threshold else "low_confidence"
            return ClassificationResult(
                output=llm_result,
                routed_to=routed,
                classification_ms=elapsed,
                layer_used="llm",
                fingerprint=fingerprint,
                is_duplicate=is_duplicate,
            )

        # ── No result at all ─────────────────────────────────────────────────
        elapsed = (time.perf_counter() - start) * 1000
        fallback = ClassifierOutput(
            failure_type=FailureType.UNKNOWN,
            confidence=0.30,
            evidence=[],
            reason="No rule matched and LLM fallback is disabled.",
            layer="none",
            fingerprint=fingerprint,
        )
        return ClassificationResult(
            output=fallback,
            routed_to="low_confidence",
            classification_ms=elapsed,
            layer_used="none",
            fingerprint=fingerprint,
            is_duplicate=is_duplicate,
        )

    def _run_llm(self, trace: NormalizedTrace) -> ClassifierOutput:
        try:
            return self.llm_classifier.classify(trace)
        except Exception as e:
            logger.error("LLM classifier error: %s", e)
            return ClassifierOutput(
                failure_type=FailureType.UNKNOWN,
                confidence=0.30,
                evidence=[],
                reason=f"LLM classifier error: {str(e)[:100]}",
                layer="llm",
                fingerprint=trace.fingerprint(),
            )

    def _combine(
        self,
        rule_result: ClassifierOutput,
        llm_result: ClassifierOutput
    ) -> ClassifierOutput:
        """
        Merges rule-based and LLM results when both fire.
        Agreement → boost confidence.
        Disagreement → pick higher confidence, flag the other as secondary.
        """
        if rule_result.failure_type == llm_result.failure_type:
            # Agreement → weighted average leaning toward rule (more reliable)
            combined_confidence = min(0.95, (rule_result.confidence * 0.45) + (llm_result.confidence * 0.55) + 0.05)
            all_evidence = list(set(rule_result.evidence + llm_result.evidence))
            return ClassifierOutput(
                failure_type=rule_result.failure_type,
                confidence=combined_confidence,
                evidence=all_evidence,
                reason=llm_result.reason,  # LLM reason is more descriptive
                secondary_suspect=llm_result.secondary_suspect,
                layer="combined",
                fingerprint=rule_result.fingerprint,
            )
        else:
            # Disagreement → pick higher confidence
            if rule_result.confidence >= llm_result.confidence:
                primary, secondary = rule_result, llm_result
            else:
                primary, secondary = llm_result, rule_result

            # Slight confidence penalty for disagreement
            penalized = max(0.35, primary.confidence - 0.08)
            return ClassifierOutput(
                failure_type=primary.failure_type,
                confidence=penalized,
                evidence=list(set(primary.evidence + secondary.evidence)),
                reason=f"{primary.reason} (rule and LLM disagreed — rule says {rule_result.failure_type.value}, LLM says {llm_result.failure_type.value})",
                secondary_suspect=secondary.failure_type,
                layer="combined",
                fingerprint=primary.fingerprint,
            )
