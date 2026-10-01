"""Rotas públicas da aplicação GenAI."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["operational"])
def health() -> dict[str, str]:
    """Indica que o processo HTTP está ativo."""

    return {"status": "ok"}
