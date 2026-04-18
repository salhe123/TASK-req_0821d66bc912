from fastapi import APIRouter, Depends

from app.middleware.auth import get_auth
from app.services import metrics
from app.services.rbac import AuthContext, ensure_permission

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
async def get_metrics(auth: AuthContext = Depends(get_auth)) -> dict:
    ensure_permission(auth, "audit", "read")
    return metrics.snapshot()
