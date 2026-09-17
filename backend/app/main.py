import logging
from contextlib import asynccontextmanager

from backend.app.api.v1.health import health_check
from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.core.database import init_db
from backend.app.core.errors import register_exception_handlers
from backend.app.schemas.health import HealthResponse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure structured logging
log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ai_gym_backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan event handler for startup and shutdown tasks."""
    logger.info(f"Starting {settings.PROJECT_NAME} (v{settings.VERSION}) in [{settings.ENVIRONMENT}] mode...")
    # Initialize DB schema for dev / sqlite environment
    if settings.ENVIRONMENT == "development" and "sqlite" in settings.DATABASE_URL:
        try:
            await init_db()
            logger.info("Local database tables verified.")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")


def create_application() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Production-grade REST & Real-time WebSocket API for AI-powered exercise form coaching and repetition telemetry.",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    # Register standardized exception handlers
    register_exception_handlers(app)

    # CORS configuration
    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Mount API routers
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Root health endpoint
    app.add_api_route(
        "/health",
        health_check,
        methods=["GET"],
        response_model=HealthResponse,
        tags=["Health"],
        summary="Root Health Check",
    )

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )
