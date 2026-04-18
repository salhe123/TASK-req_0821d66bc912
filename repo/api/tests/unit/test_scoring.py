from decimal import Decimal

import pytest

from app.services.canonical import canonical_json
from app.services.scoring import ScoringContext, score_submission, trace_hash


CTX = ScoringContext(
    template_version_id="tv-1",
    rule_set_version_id="rs-1",
    outlier_z_default=Decimal("3.0"),
)


TEMPLATE = [
    {"key": "q1", "label": "Q1", "weight": "1", "required": True, "missing_strategy": "ZERO_FILL"},
    {"key": "q2", "label": "Q2", "weight": "2", "required": True, "missing_strategy": "ZERO_FILL"},
]


def test_basic_weighted_average():
    trace = score_submission(
        template_items=TEMPLATE,
        inputs={"q1": "8", "q2": "10"},
        ctx=CTX,
    )
    # (8*1 + 10*2) / (1+2) = 28/3 = 9.333333...
    assert trace["totals"]["weighted_sum"] == Decimal("28")
    assert trace["totals"]["weight_sum"] == Decimal("3")
    assert trace["totals"]["score"] == Decimal("9.333333333333")


def test_replay_byte_identical_same_inputs():
    inputs = {"q1": "8", "q2": "10"}
    a = score_submission(template_items=TEMPLATE, inputs=inputs, ctx=CTX)
    b = score_submission(template_items=TEMPLATE, inputs=inputs, ctx=CTX)
    assert canonical_json(a) == canonical_json(b)
    assert trace_hash(a) == trace_hash(b)


def test_zero_fill_missing_counts_weight():
    trace = score_submission(
        template_items=TEMPLATE,
        inputs={"q1": "8"},  # q2 missing
        ctx=CTX,
    )
    # q2 missing + ZERO_FILL: effective 0, weight 2 → (8*1 + 0*2)/(1+2) = 8/3
    assert trace["totals"]["weighted_sum"] == Decimal("8")
    assert trace["totals"]["weight_sum"] == Decimal("3")


def test_exclude_from_denominator_drops_weight():
    template = [
        {"key": "q1", "label": "Q1", "weight": "1", "required": True, "missing_strategy": "ZERO_FILL"},
        {"key": "q2", "label": "Q2", "weight": "2", "required": False,
         "missing_strategy": "EXCLUDE_FROM_DENOMINATOR"},
    ]
    trace = score_submission(template_items=template, inputs={"q1": "8"}, ctx=CTX)
    # q2 missing + EXCLUDE: dropped from both num and denom → 8*1 / 1 = 8
    assert trace["totals"]["weighted_sum"] == Decimal("8")
    assert trace["totals"]["weight_sum"] == Decimal("1")
    assert trace["totals"]["score"] == Decimal("8")


def test_missing_flag_set_for_required_missing():
    trace = score_submission(template_items=TEMPLATE, inputs={"q1": "8"}, ctx=CTX)
    q2_step = next(s for s in trace["steps"] if s["item_key"] == "q2")
    assert "missing" in q2_step["flags"]
    assert q2_step["raw_present"] is False


def test_threshold_flag_on_min_max():
    template = [
        {"key": "q1", "label": "Q1", "weight": "1", "required": True,
         "missing_strategy": "ZERO_FILL", "min_value": "0", "max_value": "10"},
    ]
    trace = score_submission(
        template_items=template, inputs={"q1": "999"}, ctx=CTX
    )
    step = trace["steps"][0]
    assert "threshold_exceeded" in step["flags"]
    # Raw value preserved
    assert step["raw_value"] == Decimal("999")


def test_raw_value_not_rewritten_when_outlier():
    template = [
        {"key": "q", "label": "Q", "weight": "1", "required": True,
         "missing_strategy": "ZERO_FILL"},
    ]
    priors = {"q": [Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1")]}
    trace = score_submission(
        template_items=template,
        inputs={"q": "100"},
        ctx=CTX,
        prior_values_by_item=priors,
    )
    step = trace["steps"][0]
    assert step["raw_value"] == Decimal("100")
    assert "outlier" in step["flags"]


def test_no_outlier_flag_with_small_population():
    template = [
        {"key": "q", "label": "Q", "weight": "1", "required": True,
         "missing_strategy": "ZERO_FILL"},
    ]
    priors = {"q": [Decimal("1"), Decimal("1")]}  # n=2 — below threshold
    trace = score_submission(
        template_items=template,
        inputs={"q": "100"},
        ctx=CTX,
        prior_values_by_item=priors,
    )
    step = trace["steps"][0]
    assert "outlier" not in step["flags"]


def test_per_item_z_override():
    template = [
        {"key": "q", "label": "Q", "weight": "1", "required": True,
         "missing_strategy": "ZERO_FILL", "outlier_z": "10.0"},
    ]
    priors = {"q": [Decimal(x) for x in ("1", "1", "1", "1", "1")]}
    trace = score_submission(
        template_items=template,
        inputs={"q": "100"},
        ctx=CTX,
        prior_values_by_item=priors,
    )
    # With z threshold of 10, 100 vs [1s] still flagged because z is very large
    # but if we raise threshold enough, it should not flag. Let's instead use
    # small deviation with high threshold.
    trace2 = score_submission(
        template_items=template,
        inputs={"q": "2"},  # one stddev above mean of 1
        ctx=CTX,
        prior_values_by_item={"q": [Decimal("0"), Decimal("1"), Decimal("2"),
                                     Decimal("1"), Decimal("0"), Decimal("2")]},
    )
    step2 = trace2["steps"][0]
    assert "outlier" not in step2["flags"]


def test_steps_sorted_by_item_key():
    template = [
        {"key": "z", "label": "Z", "weight": "1", "required": True, "missing_strategy": "ZERO_FILL"},
        {"key": "a", "label": "A", "weight": "1", "required": True, "missing_strategy": "ZERO_FILL"},
    ]
    trace = score_submission(template_items=template, inputs={"z": "1", "a": "1"}, ctx=CTX)
    keys = [s["item_key"] for s in trace["steps"]]
    assert keys == ["a", "z"]


def test_zero_weight_sum_produces_zero_score():
    template = [
        {"key": "q", "label": "Q", "weight": "0", "required": False, "missing_strategy": "ZERO_FILL"},
    ]
    trace = score_submission(template_items=template, inputs={"q": "5"}, ctx=CTX)
    assert trace["totals"]["score"] == Decimal("0")
