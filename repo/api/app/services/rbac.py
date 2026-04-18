from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Callable, Iterable

from app.core.errors import Forbidden


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    username: str
    roles: tuple[str, ...]
    permissions: frozenset[tuple[str, str]]
    field_view_allowlist: frozenset[str]
    session_id: str
    csrf_token: str

    def has_permission(self, resource: str, action: str) -> bool:
        if ("*", "*") in self.permissions:
            return True
        return (resource, action) in self.permissions

    def can_view_field(self, field: str) -> bool:
        if "*" in self.field_view_allowlist:
            return True
        return field in self.field_view_allowlist


def ensure_permission(ctx: AuthContext, resource: str, action: str) -> None:
    if not ctx.has_permission(resource, action):
        raise Forbidden(
            error="permission_denied",
            message=f"missing permission {resource}:{action}",
        )


def require_permission(resource: str, action: str) -> Callable:
    """Decorator for FastAPI handlers: expects an `auth` kwarg of AuthContext."""

    def wrapper(func: Callable) -> Callable:
        @wraps(func)
        async def inner(*args, **kwargs):
            auth = kwargs.get("auth")
            if not isinstance(auth, AuthContext):
                raise Forbidden(error="auth_context_missing", message="auth context required")
            ensure_permission(auth, resource, action)
            return await func(*args, **kwargs)

        return inner

    return wrapper


def merge_allowlists(per_role_lists: Iterable[Iterable[str]]) -> frozenset[str]:
    out: set[str] = set()
    for lst in per_role_lists:
        for entry in lst:
            out.add(entry)
    return frozenset(out)
