from argon2 import PasswordHasher, exceptions

from app.core.errors import ApiError
from app.core.settings import get_settings

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


class WeakPassword(ApiError):
    def __init__(self, message: str):
        super().__init__(error="weak_password", message=message, status_code=400)


def validate_strength(password: str) -> None:
    settings = get_settings()
    if len(password) < settings.password_min_length:
        raise WeakPassword(f"password must be ≥ {settings.password_min_length} characters")
    if password.strip() != password:
        raise WeakPassword("password must not have leading or trailing whitespace")


def hash_password(password: str) -> str:
    validate_strength(password)
    return _hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        _hasher.verify(stored_hash, password)
        return True
    except exceptions.VerifyMismatchError:
        return False
    except exceptions.InvalidHash:
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)
