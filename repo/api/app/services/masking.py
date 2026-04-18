from __future__ import annotations

from typing import Any, Iterable

from app.services.rbac import AuthContext

MASK = "***"


def apply_mask(
    obj: dict[str, Any],
    sensitive_fields: Iterable[str],
    auth: AuthContext | None,
) -> dict[str, Any]:
    """Return a shallow copy of `obj` with values for `sensitive_fields` masked
    unless `auth` carries that field in its field_view_allowlist."""
    if auth is None:
        allowed: frozenset[str] = frozenset()
    else:
        allowed = auth.field_view_allowlist
    out: dict[str, Any] = dict(obj)
    wildcard = "*" in allowed
    for field in sensitive_fields:
        if field in out and not (wildcard or field in allowed):
            out[field] = MASK
    return out


def mask_list(
    rows: list[dict[str, Any]],
    sensitive_fields: Iterable[str],
    auth: AuthContext | None,
) -> list[dict[str, Any]]:
    fields = list(sensitive_fields)
    return [apply_mask(r, fields, auth) for r in rows]
