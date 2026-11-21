"""Configuração local do módulo GenAI."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
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
    gemini_complex_model: str | None = "gemini-3.5-flash"
    gemini_fallback_model: str | None = "gemini-3.5-flash"
    provider_order: str = "gemini,groq,openrouter"
    groq_api_key: SecretStr | None = None
    groq_model: str | None = None
    openrouter_api_key: SecretStr | None = None
    openrouter_model: str | None = None
    provider_timeout_seconds: float = Field(default=12, gt=0, allow_inf_nan=False)
    gemini_analytical_timeout_seconds: float = Field(default=20, gt=0, allow_inf_nan=False)
    openrouter_analytical_timeout_seconds: float = Field(default=36, gt=0, allow_inf_nan=False)
    provider_budget_seconds: float = Field(default=40, gt=0, allow_inf_nan=False)
    provider_cooldown_seconds: float = Field(default=60, gt=0, allow_inf_nan=False)
    response_cache_ttl_seconds: float = 300.0
    canonical_response_cache_ttl_seconds: float = 3600.0
    response_cache_rules_version: str = "2"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GENAI_",
        extra="ignore",
    )

    @field_validator("provider_order")
    @classmethod
    def validate_provider_order(cls, value: str) -> str:
        names = [name.strip().lower() for name in value.split(",")]
        if (not names or any(name not in {"gemini", "groq", "openrouter"} for name in names)
                or len(set(names)) != len(names)):
            raise ValueError("Ordem de provedores contém nomes desconhecidos ou repetidos.")
        return ",".join(names)


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância reutilizável da configuração."""

    return Settings()
