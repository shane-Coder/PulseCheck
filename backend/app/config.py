from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://pulsecheck:pulsecheck@db:5432/pulsecheck"
    redis_url: str = "redis://redis:6379/0"

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
