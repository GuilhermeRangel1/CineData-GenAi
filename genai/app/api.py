"""Rotas públicas da aplicação GenAI."""

import asyncio
import json
import logging
from functools import lru_cache
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.agent import AgentClarification, AgentError, AgentGuardrail, AgentService, AgentUnsupported
from app.agent_models import ConversationContext
from app.config import get_settings
from app.errors import GoldDatabaseError, ProviderConfigurationError, QueryTimeoutError
from app.gemini_adapter import GeminiToolCallingModel
from app.gold_database import GoldDatabase
from app.insight_service import InsightService
from app.response_cache import ResponseCache, gold_version, make_cache_key
from app.sql_executor import GoldQueryExecutor
from app.semantic_search import SynopsisSearchIndex

router = APIRouter()
v1_router = APIRouter()
logger = logging.getLogger(__name__)


class ConversationTurn(BaseModel):
    """Contexto resumido no navegador e descartado após a requisição."""

    question: str = Field(min_length=1, max_length=1000)
    metric: str | None = Field(default=None, max_length=160)
    unit: str | None = Field(default=None, max_length=100)
    period: str | None = Field(default=None, max_length=160)
    population: str | None = Field(default=None, max_length=300)


class QuestionRequest(BaseModel):
    """Entrada pública para uma pergunta analítica."""

    question: str = Field(min_length=1, max_length=1000)
    context: list[ConversationTurn] = Field(default_factory=list, max_length=3)
    conversation_id: str | None = Field(default=None, min_length=12, max_length=80)

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

    source: Literal["gold", "platform", "semantic", "mixed"] = "gold"
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
    cached: bool = False


class QuestionResponse(BaseModel):
    """Resposta pública com texto, evidência tabular e contexto da métrica."""

    status: Literal["success"] = "success"
    answer: str
    rows: list[dict[str, Any]]
    insights: list[str]
    metadata: QuestionMetadata


def _stream_event(event_type: str, **payload: Any) -> str:
    """Serializa um evento NDJSON pequeno para consumo incremental no navegador."""

    return json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n"


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
        model = GeminiToolCallingModel(
            api_key,
            model=settings.gemini_model,
            complex_model=settings.gemini_complex_model,
            fallback_model=settings.gemini_fallback_model,
        )
    else:
        model = _UnconfiguredModel()
    database = GoldDatabase(settings.gold_database_path, settings.gold_timeout_seconds)
    executor = GoldQueryExecutor(
        database,
        timeout_seconds=settings.gold_timeout_seconds,
        complex_timeout_seconds=settings.gold_complex_timeout_seconds,
        pair_query_timeout_seconds=settings.gold_pair_query_timeout_seconds,
    )
    return AgentService(
        model,
        executor,
        insight_service=InsightService(model),
        semantic_search=SynopsisSearchIndex(database),
    )


@lru_cache(maxsize=1)
def get_response_cache() -> ResponseCache:
    """Reutiliza um cache local, sem persistir conversas após reiniciar o serviço."""

    settings = get_settings()
    return ResponseCache(ttl_seconds=settings.response_cache_ttl_seconds)


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

    context = tuple(
        ConversationContext(
            question=turn.question.strip(),
            metric=turn.metric,
            unit=turn.unit,
            period=turn.period,
            population=turn.population,
        )
        for turn in payload.context
    )
    cache_key = None
    if payload.conversation_id and isinstance(service, AgentService):
        settings = get_settings()
        try:
            cache_key = make_cache_key(
                conversation_id=payload.conversation_id,
                question=payload.question,
                context=context,
                gold_revision=gold_version(service.executor.database.path),
                rules_version=settings.response_cache_rules_version,
            )
        except OSError:
            cache_key = None
    cached_response = get_response_cache().get(cache_key) if cache_key else None

    try:
        response = cached_response or service.answer(payload.question, context)
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
    except AgentGuardrail as exc:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "error": {
                    "code": "guardrail_rejected",
                    "message": str(exc),
                    "details": None,
                },
            },
        )
    except AgentUnsupported as exc:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "error": {
                    "code": "unsupported_question",
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

    if cache_key and cached_response is None:
        get_response_cache().put(cache_key, response)

    return QuestionResponse(
        status="success",
        answer=response.answer,
        rows=list(response.rows),
        insights=list(response.insights),
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
            cached=cached_response is not None,
        ),
    )


@v1_router.post("/questions/stream", tags=["questions"])
async def stream_answer_question(
    payload: QuestionRequest,
    service: AgentService = Depends(get_agent_service),  # noqa: B008
) -> StreamingResponse:
    """Entrega progresso e resultado no mesmo fluxo sem expor detalhes internos."""

    async def events():
        yield _stream_event(
            "progress",
            stage="understanding",
            message="Entendendo sua pergunta…",
        )
        # Garante que o primeiro estado seja perceptível também em respostas
        # locais muito rápidas, sem transformar o processamento em espera.
        await asyncio.sleep(0.16)
        yield _stream_event(
            "progress",
            stage="searching",
            message="Buscando as informações certas…",
        )
        await asyncio.sleep(0.16)

        try:
            response = await asyncio.to_thread(answer_question, payload, service)
        except HTTPException as exc:
            yield _stream_event(
                "error",
                status=exc.status_code,
                error={
                    "code": "service_error",
                    "message": str(exc.detail),
                    "details": None,
                },
            )
            return
        except Exception:
            logger.exception("Falha inesperada no fluxo de progresso GenAI.")
            yield _stream_event(
                "error",
                status=500,
                error={
                    "code": "stream_error",
                    "message": "Não foi possível concluir a pergunta.",
                    "details": None,
                },
            )
            return

        if isinstance(response, JSONResponse):
            content = json.loads(bytes(response.body).decode("utf-8"))
            yield _stream_event(
                "error",
                status=response.status_code,
                error=content.get(
                    "error",
                    {
                        "code": "request_error",
                        "message": "Não foi possível concluir a pergunta.",
                        "details": None,
                    },
                ),
            )
            return

        if response.metadata.cached:
            stage = "cache"
            message = "Resposta recente encontrada…"
        elif response.metadata.source == "platform":
            stage = "guide"
            message = "Preparando a orientação do CineData…"
        elif response.metadata.source in {"semantic", "mixed"}:
            stage = "hybrid"
            message = "Relacionando catálogo e sinopses…"
        else:
            stage = "preparing"
            message = "Organizando os dados encontrados…"

        yield _stream_event("progress", stage=stage, message=message)
        # Mantém a etapa final perceptível mesmo quando o proxy entrega os
        # últimos eventos quase juntos, sem acrescentar atraso relevante.
        await asyncio.sleep(0.12)
        yield _stream_event("result", data=response.model_dump(mode="json"))

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
