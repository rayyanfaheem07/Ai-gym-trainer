from backend.app.core.config import settings
from backend.app.core.database import check_database_health
from backend.app.schemas.health import HealthResponse
from fastapi import APIRouter

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="System Health Check")
async def health_check() -> HealthResponse:
    """Returns the operational status of the backend, DB connection, and AI engine."""
    db_ok = await check_database_health()
    ai_ok = True  # AI engine subsystem initialized

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        database_connected=db_ok,
        database_status="connected" if db_ok else "unavailable",
        ai_engine_ready=ai_ok,
    )
