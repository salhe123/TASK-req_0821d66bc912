"""Feature schema hashing.

A feature schema is a list of feature descriptors; each descriptor is a tuple of:
  (name, dtype, transform, source_query_hash)

The hash is *order-insensitive* w.r.t. the input list — we always sort by name
before hashing so two schemas that are logical equivalents but specified in
different orders compare equal.
"""
from __future__ import annotations

import hashlib
import json
from typing import Mapping, Sequence


REQUIRED_FIELDS = ("name", "dtype", "transform", "source_query_hash")


def canonicalize(features: Sequence[Mapping]) -> list[list[str]]:
    normalized = []
    for f in features:
        missing = [k for k in REQUIRED_FIELDS if k not in f]
        if missing:
            raise ValueError(f"feature missing required field(s): {missing}")
        normalized.append([str(f[k]) for k in REQUIRED_FIELDS])
    # Sort by feature name for order-independence
    normalized.sort(key=lambda row: row[0])
    return normalized


def feature_schema_hash(features: Sequence[Mapping]) -> str:
    canon = canonicalize(features)
    serialized = json.dumps(canon, separators=(",", ":"), sort_keys=False, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def diff_schemas(
    expected: Sequence[Mapping], got: Sequence[Mapping]
) -> tuple[list[str], list[str]]:
    """Return (missing_in_got, extra_in_got) feature names, comparing by name only."""
    expected_names = {f["name"] for f in expected}
    got_names = {f["name"] for f in got}
    missing = sorted(expected_names - got_names)
    extra = sorted(got_names - expected_names)
    return missing, extra
