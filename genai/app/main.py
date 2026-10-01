"""Ponto de entrada da API FastAPI do módulo GenAI."""

from fastapi import FastAPI

from app.api import router
from app.config import get_settings


def create_app() -> FastAPI:
    """Cria a aplicação sem inicializar banco, modelo ou provedor."""

    settings = get_settings()
    application = FastAPI(title=settings.service_name, version="0.1.0")
    application.include_router(router)
    return application


app = create_app()
