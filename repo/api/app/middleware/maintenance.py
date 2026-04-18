from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.services import maintenance


ADMIN_ROLE = "Administrator"


class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    """When a restore is staged, only requests from an Administrator session
    can continue. Auth itself (login, health) is exempt so an admin can still
    sign in to commit or abort."""

    EXEMPT_PATHS = {
        "/api/health",
        "/api/health/ready",
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/me",
    }
    EXEMPT_PREFIXES = ("/api/admin/",)

    async def dispatch(self, request: Request, call_next):
        if not maintenance.is_active():
            return await call_next(request)

        path = request.url.path
        if path in self.EXEMPT_PATHS or any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return await call_next(request)

        return JSONResponse(
            status_code=503,
            content={
                "error": "maintenance",
                "message": "system is under restore maintenance",
                "details": maintenance.snapshot(),
            },
        )
