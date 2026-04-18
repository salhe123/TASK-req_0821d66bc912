from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.settings import get_settings

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def run_migrations() -> None:
    settings = get_settings()
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", settings.database_url_sync)
    command.upgrade(cfg, "head")
