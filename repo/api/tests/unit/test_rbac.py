import pytest

from app.core.errors import Forbidden
from app.services.rbac import AuthContext, ensure_permission, require_permission


def ctx(permissions=(), allowlist=()):
    return AuthContext(
        user_id="u",
        username="user",
        roles=("R",),
        permissions=frozenset(permissions),
        field_view_allowlist=frozenset(allowlist),
        session_id="s",
        csrf_token="c",
    )


def test_has_permission_exact_match():
    a = ctx(permissions=[("cycle", "participate")])
    assert a.has_permission("cycle", "participate")
    assert not a.has_permission("cycle", "manage")


def test_wildcard_admin_has_everything():
    a = ctx(permissions=[("*", "*")])
    assert a.has_permission("anything", "anything")


def test_ensure_permission_raises_forbidden():
    a = ctx(permissions=[])
    with pytest.raises(Forbidden) as ei:
        ensure_permission(a, "x", "y")
    assert ei.value.error == "permission_denied"


@pytest.mark.asyncio
async def test_require_permission_decorator_blocks():
    @require_permission("user", "manage")
    async def handler(*, auth):
        return "ok"

    with pytest.raises(Forbidden):
        await handler(auth=ctx())


@pytest.mark.asyncio
async def test_require_permission_decorator_allows_when_granted():
    @require_permission("user", "manage")
    async def handler(*, auth):
        return "ok"

    a = ctx(permissions=[("user", "manage")])
    assert await handler(auth=a) == "ok"


def test_can_view_field_respects_wildcard():
    a = ctx(allowlist=["*"])
    assert a.can_view_field("anything")
