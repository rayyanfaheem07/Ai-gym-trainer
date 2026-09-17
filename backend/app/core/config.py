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
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # Authentication & Security
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60


    # CORS
    CORS_ORIGINS: list[str] | str = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./ai_gym.db"

    # AI Model & Classification Paths
    TEMPORAL_MODEL_PATH: str = "models/temporal_exercise_classifier.pt"
    SKLEARN_MODEL_PATH: str = "models/exercise_classifier.joblib"
    MODEL_CONFIDENCE_THRESHOLD: float = 0.60

    # AI & LLM Engine (Ollama)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # Computer Vision & Pose Settings
    POSE_DETECTION_CONFIDENCE: float = 0.7
    POSE_TRACKING_CONFIDENCE: float = 0.7
    ENABLE_ONE_EURO_FILTER: bool = True


settings = Settings()
