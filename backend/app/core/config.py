from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações carregadas de variáveis de ambiente ou do arquivo .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "CineData API"
    project_version: str = "2026.2"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./rocketlab.db"
    backend_cors_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"
    jwt_secret_key: str | None = None
    jwt_access_token_expire_minutes: int = 60
    initial_admin_email: str | None = None
    initial_admin_name: str | None = None
    initial_admin_password: str | None = None
    tmdb_api_token: str | None = None
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"


@lru_cache
def get_settings() -> Settings:
    return Settings()
