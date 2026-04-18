import os
import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return os.environ.get("API_BASE_URL", "http://api:8000")


@pytest.fixture(scope="session")
def db_dsn() -> str:
    return os.environ.get(
        "DATABASE_DSN",
        "host=db port=5432 dbname=mgew user=mgew password=mgew",
    )
