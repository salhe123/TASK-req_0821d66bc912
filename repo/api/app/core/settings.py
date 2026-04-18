from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "test", "production"] = "development"
    bind_addr: str = "0.0.0.0:8000"

    database_url: str = Field(
        default="postgresql+asyncpg://mgew:mgew@db:5432/mgew",
        description="Async SQLAlchemy DSN for Postgres",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://mgew:mgew@db:5432/mgew",
        description="Sync DSN used by Alembic",
    )

    kek_path: Path = Field(
        default=Path("/run/secrets/kek"),
        description="Filesystem path to the Key Encryption Key; must exist at startup",
    )
    session_signing_key_path: Path = Field(
        default=Path("/run/secrets/session_signing_key"),
        description="Filesystem path to HMAC session signing key",
    )

    backup_volume: Path = Field(
        default=Path("/var/lib/mgew/backups"),
        description="Directory where encrypted nightly pg_dump archives are written",
    )

    session_token_skew_seconds: int = 60
    session_token_max_age_seconds: int = 12 * 3600
    login_lockout_threshold: int = 5
    login_lockout_window_seconds: int = 15 * 60
    password_min_length: int = 12
    cookie_secure: bool = False

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    run_migrations_on_startup: bool = True

    backup_scheduler_enabled: bool = False
    backup_scheduler_hour: int = 2  # local hour (0-23) to trigger nightly backup
    backup_scheduler_timezone: str = "UTC"
    # When true, the backup commit endpoint actually invokes `pg_restore` to
    # reapply the archive. Default false because the test harness needs the
    # state machine without the destructive side effect; production enables it.
    backup_restore_execute: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
