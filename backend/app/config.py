from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://pulsecheck:pulsecheck@db:5432/pulsecheck"
    redis_url: str = "redis://redis:6379/0"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        # Managed Postgres providers (Fly, Railway, Render, Heroku-style) hand out
        # "postgres://..." or plain "postgresql://..." — SQLAlchemy needs the
        # psycopg2 dialect prefix to pick the right driver.
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg2://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg2://", 1)
        return v

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080

    base_url: str = "http://localhost:8000"
    environment: str = "development"

    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "alerts@pulsecheck.local"
    smtp_use_tls: bool = True

    overdue_check_interval_seconds: int = 60


settings = Settings()
