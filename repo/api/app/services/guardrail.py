"""Guardrail breach detector.

Triggers auto-rollback when any of:
  - error_rate > 2 %
  - p95_latency_ms > 150
  - disengagement > baseline + 30 % (rolling 15 min)

Inputs are in the caller's units; this service has no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass


ERROR_RATE_THRESHOLD = 0.02
P95_LATENCY_THRESHOLD_MS = 150.0
DISENGAGEMENT_DELTA = 0.30


@dataclass
class GuardrailInputs:
    error_rate: float  # 0..1
    p95_latency_ms: float
    disengagement: float  # current value
    disengagement_baseline: float  # baseline over same window


@dataclass
class GuardrailDecision:
    breached: bool
    reasons: list[str]

    def to_dict(self) -> dict:
        return {"breached": self.breached, "reasons": sorted(self.reasons)}


def evaluate(inputs: GuardrailInputs) -> GuardrailDecision:
    reasons: list[str] = []
    if inputs.error_rate > ERROR_RATE_THRESHOLD:
        reasons.append("error_rate_exceeded")
    if inputs.p95_latency_ms > P95_LATENCY_THRESHOLD_MS:
        reasons.append("p95_latency_exceeded")
    if (
        inputs.disengagement_baseline > 0
        and (inputs.disengagement - inputs.disengagement_baseline) / inputs.disengagement_baseline
        > DISENGAGEMENT_DELTA
    ):
        reasons.append("disengagement_spike")
    return GuardrailDecision(breached=bool(reasons), reasons=reasons)
