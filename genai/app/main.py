"""Ponto de entrada da API FastAPI do módulo GenAI."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router, v1_router
from app.config import get_settings


def _configure_application_logging() -> None:
    """Exibe a rota SQL e os tempos já registrados sem ampliar logs externos."""

    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s: %(name)s: %(message)s"))
        app_logger.addHandler(handler)
    app_logger.propagate = False


def create_app() -> FastAPI:
    """Cria a aplicação sem inicializar banco, modelo ou provedor."""

    _configure_application_logging()
    settings = get_settings()
    application = FastAPI(title=settings.service_name, version="0.1.0")
    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    application.include_router(router)
    application.include_router(v1_router, prefix=settings.api_prefix)
    return application


app = create_app()
