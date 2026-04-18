import pytest

from app.core.errors import ApiError
from app.services.passwords import (
    hash_password,
    verify_password,
    validate_strength,
    needs_rehash,
)


def test_hash_verify_roundtrip():
    h = hash_password("correcthorse-battery-1")
    assert verify_password("correcthorse-battery-1", h) is True
    assert verify_password("nope", h) is False


def test_hash_is_argon2id():
    h = hash_password("correcthorse-battery-1")
    assert h.startswith("$argon2id$")


def test_rejects_short_password():
    with pytest.raises(ApiError) as ei:
        validate_strength("short")
    assert ei.value.error == "weak_password"


def test_rejects_whitespace_edges():
    with pytest.raises(ApiError):
        validate_strength(" haslongenoughbutspace ")


def test_verify_rejects_invalid_hash():
    assert verify_password("anything", "not-a-hash") is False


def test_needs_rehash_false_for_fresh_hash():
    h = hash_password("correcthorse-battery-1")
    assert needs_rehash(h) is False
