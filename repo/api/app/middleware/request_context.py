import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.errors import ApiError
from app.core.logging import request_id_ctx
from app.services import metrics

logger = logging.getLogger("api.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_ctx.set(rid)
        start = time.perf_counter()
        metrics.inc_request()
        try:
            response = await call_next(request)
        except ApiError as exc:
            metrics.inc_error()
            response = JSONResponse(status_code=exc.status_code, content=exc.to_envelope())
        except Exception:
            metrics.inc_error()
            logger.exception("unhandled_exception", extra={"path": request.url.path})
            response = JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "internal error", "details": {}},
            )
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            request_id_ctx.reset(token)
        response.headers["x-request-id"] = rid
        logger.info(
            "request_complete",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
