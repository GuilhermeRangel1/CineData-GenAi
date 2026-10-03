"""Configuração local do módulo GenAI."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Opções operacionais que não dependem de um provedor externo."""

    service_name: str = "CineData GenAI"
    api_prefix: str = "/api/v1"
    max_question_length: int = 1000
    gold_database_path: Path = Path("../data/cinerocket.db")
    gold_timeout_seconds: float = 5.0
    gold_complex_timeout_seconds: float = 15.0
    gold_pair_query_timeout_seconds: float = 45.0
    cors_origins: str = "http://localhost:8080,http://localhost:5173"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_fallback_model: str | None = "gemini-3.5-flash"
    response_cache_ttl_seconds: float = 300.0
    response_cache_rules_version: str = "1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GENAI_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância reutilizável da configuração."""

    return Settings()
