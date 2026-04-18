from app.services.guardrail import GuardrailInputs, evaluate


def test_no_breach_within_budget():
    d = evaluate(
        GuardrailInputs(
            error_rate=0.01,
            p95_latency_ms=120.0,
            disengagement=0.1,
            disengagement_baseline=0.1,
        )
    )
    assert d.breached is False
    assert d.reasons == []


def test_error_rate_above_2pct_breaches():
    d = evaluate(
        GuardrailInputs(
            error_rate=0.025,
            p95_latency_ms=100.0,
            disengagement=0.1,
            disengagement_baseline=0.1,
        )
    )
    assert d.breached is True
    assert "error_rate_exceeded" in d.reasons


def test_p95_latency_above_budget_breaches():
    d = evaluate(
        GuardrailInputs(
            error_rate=0.001,
            p95_latency_ms=160.0,
            disengagement=0.1,
            disengagement_baseline=0.1,
        )
    )
    assert d.breached is True
    assert "p95_latency_exceeded" in d.reasons


def test_disengagement_30pct_above_baseline_breaches():
    d = evaluate(
        GuardrailInputs(
            error_rate=0.001,
            p95_latency_ms=100.0,
            disengagement=0.14,
            disengagement_baseline=0.10,  # 40% higher
        )
    )
    assert d.breached is True
    assert "disengagement_spike" in d.reasons


def test_disengagement_exactly_30pct_does_not_breach():
    d = evaluate(
        GuardrailInputs(
            error_rate=0.001,
            p95_latency_ms=100.0,
            disengagement=0.13,
            disengagement_baseline=0.10,  # exactly 30%
        )
    )
    assert d.breached is False


def test_disengagement_baseline_zero_ignored():
    d = evaluate(
        GuardrailInputs(
            error_rate=0.001,
            p95_latency_ms=100.0,
            disengagement=0.5,
            disengagement_baseline=0.0,
        )
    )
    assert "disengagement_spike" not in d.reasons


def test_multiple_reasons_combined():
    d = evaluate(
        GuardrailInputs(
            error_rate=0.05,
            p95_latency_ms=200.0,
            disengagement=0.2,
            disengagement_baseline=0.1,
        )
    )
    assert d.breached is True
    assert set(d.reasons) == {
        "error_rate_exceeded",
        "p95_latency_exceeded",
        "disengagement_spike",
    }
