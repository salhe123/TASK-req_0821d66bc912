from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import ApiError
from app.services import metrics


def register_error_handlers(app) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError):
        metrics.inc_error()
        return JSONResponse(status_code=exc.status_code, content=exc.to_envelope())

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException):
        metrics.inc_error()
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": _slug_for_status(exc.status_code),
                "message": str(exc.detail) if exc.detail else "",
                "details": {},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        metrics.inc_error()
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "message": "request validation failed",
                "details": {"errors": exc.errors()},
            },
        )


def _slug_for_status(code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        423: "account_locked",
        429: "rate_limited",
        503: "maintenance",
    }.get(code, "error")
