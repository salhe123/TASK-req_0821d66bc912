"""Deterministic scoring engine.

Given:
  - A template version's items (list of dicts with key/label/weight/required/missing_strategy/…)
  - A rule set version's rules (e.g. {"outlier_z_default": "3.0"})
  - A dict of raw inputs keyed by item.key
  - Optional prior values per item_key for z-score outlier flagging

It emits a trace dict with:
  - engine_version: "1"
  - template_version_id / rule_set_version_id
  - inputs: canonicalised
  - steps: one per template item, ordered by key
  - totals: weighted_sum, weight_sum, score

Missing strategies applied per item:
  - ZERO_FILL — missing raw → effective value 0, weight still counts
  - EXCLUDE_FROM_DENOMINATOR — missing raw → both value AND weight excluded

Raw values are NEVER altered; we only emit flags.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Iterable, Mapping, MutableMapping

from app.services.canonical import canonical_hash, canonical_json


ENGINE_VERSION = "1"

ZERO = Decimal("0")
SCORE_QUANTIZE = Decimal("0.000000000001")  # 12 fractional digits


@dataclass
class ScoringContext:
    template_version_id: str
    rule_set_version_id: str
    outlier_z_default: Decimal = Decimal("3.0")


def _to_decimal(value) -> Decimal:
    if value is None:
        raise ValueError("cannot convert None to Decimal")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ValueError("booleans are not accepted as numeric inputs")
    return Decimal(str(value))


def _stats(values: Iterable[Decimal]) -> tuple[int, Decimal, Decimal]:
    """Return (n, mean, sample_stddev). stddev = 0 when n < 2."""
    xs = list(values)
    n = len(xs)
    if n == 0:
        return (0, ZERO, ZERO)
    total = sum(xs, ZERO)
    mean = total / Decimal(n)
    if n < 2:
        return (n, mean, ZERO)
    sq_dev = sum((x - mean) * (x - mean) for x in xs)
    variance = sq_dev / Decimal(n - 1)
    # Decimal has no sqrt on the class itself in < 3.12; use Decimal.sqrt (context-aware).
    stddev = variance.sqrt() if variance > 0 else ZERO
    return (n, mean, stddev)


def score_submission(
    *,
    template_items: list[Mapping[str, object]],
    inputs: Mapping[str, object],
    ctx: ScoringContext,
    prior_values_by_item: Mapping[str, list[Decimal]] | None = None,
) -> dict:
    """Produce a canonical trace dict (ready for canonical_json/hash).

    `prior_values_by_item` is an optional mapping item_key -> list of prior raw
    Decimal values to compute z-scores against for outlier detection.
    """
    priors = prior_values_by_item or {}
    steps: list[dict] = []
    weighted_sum = ZERO
    weight_sum = ZERO

    canonical_inputs: dict[str, object] = {}
    items_sorted = sorted(template_items, key=lambda it: str(it["key"]))

    for item in items_sorted:
        key = str(item["key"])
        weight = _to_decimal(item.get("weight", "0"))
        strategy = str(item.get("missing_strategy", "ZERO_FILL"))
        required = bool(item.get("required", True))
        min_value = item.get("min_value")
        max_value = item.get("max_value")
        override_z = item.get("outlier_z")

        raw_input = inputs.get(key)
        raw_present = raw_input is not None
        flags: list[str] = []

        if raw_present:
            raw_value = _to_decimal(raw_input)
            canonical_inputs[key] = raw_value
            effective_value = raw_value
            effective_weight = weight

            # Threshold check
            if min_value is not None and raw_value < _to_decimal(min_value):
                flags.append("threshold_exceeded")
            elif max_value is not None and raw_value > _to_decimal(max_value):
                flags.append("threshold_exceeded")

            # Outlier check (requires ≥3 priors to be meaningful)
            z_threshold = _to_decimal(override_z) if override_z is not None else ctx.outlier_z_default
            prior_list = priors.get(key, [])
            n, mean, stddev = _stats(prior_list)
            if n >= 3:
                if stddev == 0:
                    # Zero-variance prior: any deviation is an outlier.
                    if raw_value != mean:
                        flags.append("outlier")
                else:
                    z = abs((raw_value - mean) / stddev)
                    if z > z_threshold:
                        flags.append("outlier")
        else:
            raw_value = None
            canonical_inputs[key] = None
            if required:
                flags.append("missing")
            if strategy == "ZERO_FILL":
                effective_value = ZERO
                effective_weight = weight
            elif strategy == "EXCLUDE_FROM_DENOMINATOR":
                effective_value = ZERO
                effective_weight = ZERO
            else:
                raise ValueError(f"unknown missing_strategy: {strategy}")

        weighted_sum += effective_value * effective_weight
        weight_sum += effective_weight

        steps.append(
            {
                "effective_value": effective_value,
                "effective_weight": effective_weight,
                "flags": sorted(flags),
                "item_key": key,
                "missing_strategy": strategy,
                "raw_present": raw_present,
                "raw_value": raw_value if raw_present else None,
                "weight": weight,
            }
        )

    score = (
        (weighted_sum / weight_sum).quantize(SCORE_QUANTIZE, rounding=ROUND_HALF_EVEN)
        if weight_sum != 0
        else ZERO
    )

    trace: dict = {
        "engine_version": ENGINE_VERSION,
        "inputs": canonical_inputs,
        "rule_set_version_id": ctx.rule_set_version_id,
        "steps": steps,
        "template_version_id": ctx.template_version_id,
        "totals": {
            "score": score,
            "weight_sum": weight_sum,
            "weighted_sum": weighted_sum,
        },
    }
    return trace


def trace_hash(trace: dict) -> str:
    return canonical_hash(trace)


def trace_canonical_json(trace: dict) -> str:
    return canonical_json(trace)
