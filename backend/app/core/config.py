from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General Project Info
    PROJECT_NAME: str = "Real-Time AI Gym Trainer"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"

    # Server Binding
    BACKEND_HOST: str = "0.0.0.0"  # nosec: B104
    BACKEND_PORT: int = 8000

    # Authentication & Security
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Rate Limiting Settings
    ENABLE_RATE_LIMITING: bool = True
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 10
    RATE_LIMIT_REGISTER_PER_MINUTE: int = 5
    RATE_LIMIT_COACH_PER_MINUTE: int = 10
    RATE_LIMIT_WS_CONNECT_PER_MINUTE: int = 30

    # CORS
    CORS_ORIGINS: list[str] | str = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("JWT_SECRET_KEY cannot be empty.")
        return v

    def validate_production_security(self) -> None:
        """Validates that production environment has secure secrets and configuration."""
        if self.ENVIRONMENT.lower() in ("production", "prod"):
            insecure_defaults = {
                "dev-secret-key-change-in-production",
                "dev-secret-key-change-in-production-use-openssl-rand-hex-32",
                "secret",
                "changeme",
            }
            if self.JWT_SECRET_KEY in insecure_defaults or "dev-secret" in self.JWT_SECRET_KEY.lower():
                raise ValueError(
                    "Insecure default JWT_SECRET_KEY detected in production mode. "
                    "A unique, cryptographically strong secret must be provided."
                )
            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY for production must be at least 32 characters long."
                )

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./ai_gym.db"

    # AI Model & Classification Paths
    TEMPORAL_MODEL_PATH: str = "models/temporal_exercise_classifier.pt"
    SKLEARN_MODEL_PATH: str = "models/exercise_classifier.joblib"
    MODEL_CONFIDENCE_THRESHOLD: float = 0.60

    # AI & LLM Engine (Ollama)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_TIMEOUT_SECONDS: float = 30.0

    # Computer Vision & Pose Settings
    POSE_DETECTION_CONFIDENCE: float = 0.7
    POSE_TRACKING_CONFIDENCE: float = 0.7
    ENABLE_ONE_EURO_FILTER: bool = True

    # Performance & Streaming Settings (Phase 15)
    REALTIME_PROCESSING_FPS: int = 30
    FRAME_MAX_WIDTH: int = 1280
    FRAME_MAX_HEIGHT: int = 720
    WEBSOCKET_MAX_MESSAGE_SIZE: int = 1_048_576


settings = Settings()
