import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.middleware.error_envelope import register_error_handlers
from app.middleware.maintenance import MaintenanceModeMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.routes.admin_audit import router as admin_audit_router
from app.routes.admin_backups import router as admin_backups_router
from app.routes.admin_roles import router as admin_roles_router
from app.routes.admin_users import router as admin_users_router
from app.routes.assignments import router as assignments_router
from app.routes.auth import router as auth_router
from app.routes.cycles import router as cycles_router
from app.routes.experiments import router as experiments_router
from app.routes.feedback import router as feedback_router
from app.routes.health import router as health_router
from app.routes.inference import router as inference_router
from app.routes.metrics import router as metrics_router
from app.routes.models import router as models_router
from app.routes.plans import router as plans_router
from app.routes.rule_sets import router as rule_sets_router
from app.routes.share import router as share_router
from app.routes.submissions import router as submissions_router
from app.routes.templates import router as templates_router

logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.run_migrations_on_startup:
        try:
            from app.core.migrate import run_migrations

            run_migrations()
            logger.info("migrations_applied")
        except Exception:
            logger.exception("migrations_failed")
            raise
    scheduler = None
    if settings.backup_scheduler_enabled:
        from app.services.backup_scheduler import get_scheduler

        scheduler = get_scheduler()
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            await scheduler.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Model Governance & Evaluation Workbench API",
        version="0.1.0",
        docs_url="/api/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.environment != "production" else None,
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(MaintenanceModeMiddleware)
    register_error_handlers(app)

    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(admin_users_router, prefix="/api")
    app.include_router(admin_roles_router, prefix="/api")
    app.include_router(admin_audit_router, prefix="/api")
    app.include_router(admin_backups_router, prefix="/api")
    app.include_router(templates_router, prefix="/api")
    app.include_router(cycles_router, prefix="/api")
    app.include_router(assignments_router, prefix="/api")
    app.include_router(submissions_router, prefix="/api")
    app.include_router(plans_router, prefix="/api")
    app.include_router(rule_sets_router, prefix="/api")
    app.include_router(share_router, prefix="/api")
    app.include_router(models_router, prefix="/api")
    app.include_router(experiments_router, prefix="/api")
    app.include_router(inference_router, prefix="/api")
    app.include_router(metrics_router, prefix="/api")
    app.include_router(feedback_router, prefix="/api")

    return app


app = create_app()
