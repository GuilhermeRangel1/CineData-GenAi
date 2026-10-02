"""Ponto de entrada da API FastAPI do módulo GenAI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router, v1_router
from app.config import get_settings


def create_app() -> FastAPI:
    """Cria a aplicação sem inicializar banco, modelo ou provedor."""

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
