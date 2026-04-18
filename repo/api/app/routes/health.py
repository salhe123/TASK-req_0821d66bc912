from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import get_engine
from app.core.settings import get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def health_ready() -> dict[str, object]:
    settings = get_settings()
    checks: dict[str, str] = {}

    kek_ok = settings.kek_path.exists()
    checks["kek"] = "ok" if kek_ok else "missing"

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "unavailable"

    overall_ok = all(v == "ok" for v in checks.values())
    payload = {"status": "ok" if overall_ok else "degraded", "checks": checks}
    if not overall_ok:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=payload)
    return payload
