"""Configuração local do módulo GenAI."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Opções operacionais que não dependem de um provedor externo."""

    service_name: str = "CineData GenAI"
    api_prefix: str = "/api/v1"
    max_question_length: int = 1000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GENAI_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância reutilizável da configuração."""

    return Settings()
