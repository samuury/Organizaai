"""Configurações carregadas do ambiente."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações centrais da aplicação."""

    database_url: str = "postgresql+psycopg://organizaai:organizaai_dev@localhost:5432/organizaai"
    jwt_secret_key: str = "change-this-development-secret"
    storage_path: Path = Path("storage")
    ocr_language: str = "por"
    api_public_url: str = "http://localhost:8000"
    rate_limit_storage_uri: str = "memory://"
    frontend_origin: str = "http://localhost:5173"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_to: str | None = None
    smtp_starttls: bool = True
    critical_webhook_url: str | None = None
    critical_webhook_secret: str | None = None
    alert_window_minutes: int = Field(default=10, ge=1)
    ocr_mass_failure_threshold: int = Field(default=5, ge=1)
    suspicious_access_threshold: int = Field(default=5, ge=1)
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-5-5"

    model_config = SettingsConfigDict(env_file=[".env", "../.env"], extra="ignore")


settings = Settings()