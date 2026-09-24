from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    META_APP_ID: str
    META_APP_SECRET: str
    META_REDIRECT_URI: str
    META_API_VERSION: str = "v26.0"
    FRONTEND_URL: str = "http://localhost:8501"
    DATABASE_URL: str
    TOKEN_ENCRYPTION_KEY: str

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()