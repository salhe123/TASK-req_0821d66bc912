from decimal import Decimal

import pytest

from app.services.canonical import canonical_hash, canonical_json


def test_sorted_keys():
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_nested_sort():
    assert canonical_json({"z": {"b": 1, "a": 2}}) == '{"z":{"a":2,"b":1}}'


def test_decimal_one_point_zero_collapses_to_one():
    assert canonical_json({"x": Decimal("1.0")}) == '{"x":"1"}'
    assert canonical_json({"x": Decimal("1")}) == '{"x":"1"}'


def test_decimal_preserves_fraction():
    assert canonical_json({"x": Decimal("1.5")}) == '{"x":"1.5"}'


def test_hash_stable_across_key_order():
    a = canonical_hash({"a": 1, "b": 2})
    b = canonical_hash({"b": 2, "a": 1})
    assert a == b


def test_hash_is_sha256_hex():
    h = canonical_hash({"a": 1})
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_booleans_preserved():
    assert canonical_json({"t": True, "f": False}) == '{"f":false,"t":true}'


def test_none_preserved():
    assert canonical_json({"x": None}) == '{"x":null}'


def test_list_order_preserved():
    assert canonical_json({"xs": [3, 1, 2]}) == '{"xs":[3,1,2]}'


def test_rejects_non_finite_decimal():
    with pytest.raises(ValueError):
        canonical_json({"x": Decimal("Infinity")})


def test_float_coerced_via_decimal():
    # 0.1 → "0.1" (not the long binary repr)
    assert canonical_json({"x": 0.1}) == '{"x":"0.1"}'
