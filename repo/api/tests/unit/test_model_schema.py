import pytest

from app.services.model_schema import (
    canonicalize,
    diff_schemas,
    feature_schema_hash,
)


FEATS = [
    {"name": "a", "dtype": "float", "transform": "identity", "source_query_hash": "q1"},
    {"name": "b", "dtype": "int", "transform": "log", "source_query_hash": "q2"},
]


def test_hash_is_stable():
    assert feature_schema_hash(FEATS) == feature_schema_hash(FEATS)


def test_hash_is_order_independent():
    assert feature_schema_hash(FEATS) == feature_schema_hash(list(reversed(FEATS)))


def test_hash_is_key_order_independent():
    shuffled = [
        {"transform": "identity", "name": "a", "source_query_hash": "q1", "dtype": "float"},
        {"source_query_hash": "q2", "name": "b", "dtype": "int", "transform": "log"},
    ]
    assert feature_schema_hash(FEATS) == feature_schema_hash(shuffled)


def test_hash_changes_on_dtype_change():
    altered = [dict(FEATS[0], dtype="int"), FEATS[1]]
    assert feature_schema_hash(FEATS) != feature_schema_hash(altered)


def test_hash_changes_on_transform_change():
    altered = [dict(FEATS[0], transform="square"), FEATS[1]]
    assert feature_schema_hash(FEATS) != feature_schema_hash(altered)


def test_hash_changes_on_source_query_hash_change():
    altered = [dict(FEATS[0], source_query_hash="qX"), FEATS[1]]
    assert feature_schema_hash(FEATS) != feature_schema_hash(altered)


def test_missing_required_field_raises():
    with pytest.raises(ValueError):
        feature_schema_hash([{"name": "a", "dtype": "float", "transform": "identity"}])


def test_diff_schemas_identifies_missing_and_extra():
    expected = [
        {"name": "a", "dtype": "f", "transform": "i", "source_query_hash": "1"},
        {"name": "b", "dtype": "f", "transform": "i", "source_query_hash": "1"},
    ]
    got = [
        {"name": "a", "dtype": "f", "transform": "i", "source_query_hash": "1"},
        {"name": "c", "dtype": "f", "transform": "i", "source_query_hash": "1"},
    ]
    missing, extra = diff_schemas(expected, got)
    assert missing == ["b"]
    assert extra == ["c"]


def test_canonicalize_sorted_by_name():
    rows = canonicalize(FEATS)
    names = [r[0] for r in rows]
    assert names == sorted(names)
