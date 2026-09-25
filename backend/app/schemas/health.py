from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    database_connected: bool
    database_status: str | None = None
    ai_engine_ready: bool

