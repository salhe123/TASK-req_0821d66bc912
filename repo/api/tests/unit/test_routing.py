import pytest

from app.services.routing import bucket_for, pick_arm


def test_bucket_is_deterministic():
    assert bucket_for("subject-1") == bucket_for("subject-1")


def test_bucket_in_range_0_99():
    for key in ("alice", "bob", "charlie", "dave", "eve"):
        assert 0 <= bucket_for(key) <= 99


def test_pick_arm_weight_zero_always_b():
    for key in ("a", "b", "c", "d"):
        assert pick_arm(key, 0) == "B"


def test_pick_arm_weight_hundred_always_a():
    for key in ("a", "b", "c", "d"):
        assert pick_arm(key, 100) == "A"


def test_sticky_subject_stays_in_arm_for_all_weights_above_its_bucket():
    """A subject with bucket b lands on A iff weight_a > b. So while weight_a
    moves from b+1 to 100, it remains on arm A across every intermediate weight."""
    for key in ("alpha", "beta", "gamma", "delta", "epsilon"):
        b = bucket_for(key)
        for w in range(b + 1, 101):
            assert pick_arm(key, w) == "A", (key, b, w)
        for w in range(0, b + 1):
            assert pick_arm(key, w) == "B", (key, b, w)


def test_roughly_uniform_distribution_at_50_50():
    a_count = sum(1 for i in range(1000) if pick_arm(f"subject-{i}", 50) == "A")
    # Expect ~500, allow wide band
    assert 400 < a_count < 600
