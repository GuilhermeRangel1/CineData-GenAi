"""Rotas públicas da aplicação GenAI."""

import logging
from functools import lru_cache
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.agent import AgentClarification, AgentError, AgentService
from app.config import get_settings
from app.errors import GoldDatabaseError, ProviderConfigurationError, QueryTimeoutError
from app.gemini_adapter import GeminiToolCallingModel
from app.gold_database import GoldDatabase
from app.sql_executor import GoldQueryExecutor

router = APIRouter()
v1_router = APIRouter()
logger = logging.getLogger(__name__)


class QuestionRequest(BaseModel):
    """Entrada pública para uma pergunta analítica."""

    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        """Remove espaços externos e rejeita perguntas sem conteúdo."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("A pergunta não pode ser vazia.")
        return normalized


class QuestionMetadata(BaseModel):
    """Metadados semânticos e operacionais da consulta executada."""

    source: Literal["gold", "platform", "mixed"] = "gold"
    query_id: str | None = None
    metric: str | None = None
    unit: str | None = None
    period: str | None = None
    population: str | None = None
    limitations: str | None = None
    columns: list[str]
    row_count: int
    truncated: bool
    tool_calls: int


class QuestionResponse(BaseModel):
    """Resposta pública com texto, evidência tabular e contexto da métrica."""

    status: Literal["success"] = "success"
    answer: str
    rows: list[dict[str, Any]]
    metadata: QuestionMetadata


class _UnconfiguredModel:
    """Allows local guide answers without a provider key."""

    def complete(self, messages, tools):
        raise ProviderConfigurationError("A chave da Gemini API não foi configurada.")


@lru_cache(maxsize=1)
def get_agent_service() -> AgentService:
    """Reutiliza o cliente do provedor e seu pool de conexões entre perguntas."""

    settings = get_settings()
    api_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
    if api_key:
        model = GeminiToolCallingModel(api_key, model=settings.gemini_model)
    else:
        model = _UnconfiguredModel()
    database = GoldDatabase(settings.gold_database_path, settings.gold_timeout_seconds)
    executor = GoldQueryExecutor(
        database,
        timeout_seconds=settings.gold_timeout_seconds,
        complex_timeout_seconds=settings.gold_complex_timeout_seconds,
        pair_query_timeout_seconds=settings.gold_pair_query_timeout_seconds,
    )
    return AgentService(model, executor)


@router.get("/health", tags=["operational"])
def health() -> dict[str, str]:
    """Indica que o processo HTTP está ativo."""

    return {"status": "ok"}


@v1_router.post("/questions", response_model=QuestionResponse, tags=["questions"])
def answer_question(
    payload: QuestionRequest,
    service: AgentService = Depends(get_agent_service),  # noqa: B008
) -> QuestionResponse | JSONResponse:
    """Responde uma pergunta usando o agente e a base Gold read-only."""

    try:
        response = service.answer(payload.question)
    except GoldDatabaseError as exc:
        raise HTTPException(status_code=503, detail="A base Gold não está disponível.") from exc
    except ProviderConfigurationError as exc:
        raise HTTPException(
            status_code=503, detail="O provedor GenAI não está configurado."
        ) from exc
    except AgentClarification as exc:
        return JSONResponse(
            status_code=422,
            content={
                "status": "clarification",
                "error": {
                    "code": "ambiguous_question",
                    "message": str(exc),
                    "details": None,
                },
            },
        )
    except QueryTimeoutError:
        logger.warning("Consulta GenAI excedeu o tempo máximo.")
        return JSONResponse(
            status_code=504,
            content={
                "status": "error",
                "error": {
                    "code": "query_timeout",
                    "message": "A consulta levou mais tempo que o limite. Tente uma pergunta mais específica.",
                    "details": None,
                },
            },
        )
    except AgentError as exc:
        logger.warning("Pergunta GenAI rejeitada: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=502, detail="Não foi possível concluir a pergunta."
        ) from exc

    return QuestionResponse(
        status="success",
        answer=response.answer,
        rows=list(response.rows),
        metadata=QuestionMetadata(
            source=response.source,
            query_id=response.query_id,
            metric=response.metric,
            unit=response.unit,
            period=response.period,
            population=response.population,
            limitations=response.limitations,
            columns=list(response.columns),
            row_count=len(response.rows),
            truncated=response.truncated,
            tool_calls=response.tool_calls,
        ),
    )
