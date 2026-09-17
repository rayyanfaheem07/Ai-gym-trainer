from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    database_connected: bool
    ai_engine_ready: bool
