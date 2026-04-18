from dataclasses import dataclass
from typing import Any


@dataclass
class ApiError(Exception):
    error: str
    message: str
    status_code: int = 400
    details: dict[str, Any] | None = None

    def to_envelope(self) -> dict[str, Any]:
        return {
            "error": self.error,
            "message": self.message,
            "details": self.details or {},
        }


class NotFound(ApiError):
    def __init__(self, message: str = "not found", details: dict[str, Any] | None = None):
        super().__init__(error="not_found", message=message, status_code=404, details=details)


class Conflict(ApiError):
    def __init__(self, error: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(error=error, message=message, status_code=409, details=details)


class Unauthorized(ApiError):
    def __init__(self, error: str = "unauthorized", message: str = "unauthorized"):
        super().__init__(error=error, message=message, status_code=401)


class Forbidden(ApiError):
    def __init__(self, error: str = "forbidden", message: str = "forbidden"):
        super().__init__(error=error, message=message, status_code=403)


class Locked(ApiError):
    def __init__(self, message: str = "account locked"):
        super().__init__(error="account_locked", message=message, status_code=423)
