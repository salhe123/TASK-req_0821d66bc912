"""Canonical JSON serializer — bytes-identical output for identical logical data.

Rules:
- Keys sorted lexicographically at every nesting level.
- No insignificant whitespace (compact separators).
- Decimals serialized as their *shortest unambiguous* string form
  (Decimal("1.0") and Decimal("1") canonicalize to the same string).
- Booleans, integers, strings, None, lists, dicts supported natively.
- Everything else (UUIDs, datetimes) stringified via str().
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _canonical(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        return _decimal_to_canonical_str(value)
    if isinstance(value, float):
        # Never allow binary floats in the canonical form — force callers to
        # pass Decimals. If a float sneaks in, convert via its shortest string.
        return _decimal_to_canonical_str(Decimal(str(value)))
    if isinstance(value, str):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, list) or isinstance(value, tuple):
        return [_canonical(v) for v in value]
    if isinstance(value, dict):
        return {k: _canonical(value[k]) for k in sorted(value.keys(), key=str)}
    return str(value)


def _decimal_to_canonical_str(d: Decimal) -> str:
    # Normalize to remove trailing-zero noise, then print in plain (non-scientific) form.
    if d == 0:
        return "0"
    normalized = d.normalize()
    # normalize() can produce scientific form for large or tiny numbers; coerce.
    sign, digits, exponent = normalized.as_tuple()
    if isinstance(exponent, str):  # NaN / Infinity — reject
        raise ValueError(f"non-finite Decimal: {d}")
    # Use format spec to render fixed-point.
    return format(normalized, "f").rstrip("0").rstrip(".") if "." in format(normalized, "f") else format(normalized, "f")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
