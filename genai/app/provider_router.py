"""Fallback independente por pergunta e circuit breaker compartilhado por processo."""

import logging
import time
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock

import httpx

from app.agent_models import ModelTurn
from app.complexity_router import QuestionComplexity
from app.errors import ProviderTransientError

logger = logging.getLogger(__name__)


@dataclass
class _Question:
    remaining: float
    preferred: str | None = None


@dataclass
class _Health:
    revision: int = 0
    retry_after: float = 0
    disabled: bool = False
    failed: bool = False
    probing: bool = False


def configured_providers(settings) -> list[str]:
    """Não conta chaves vazias ou rotas sem modelo como configuração utilizável."""
    result = []
    for name in settings.provider_order.split(","):
        secret = getattr(settings, f"{name}_api_key")
        key = secret.get_secret_value().strip() if secret else ""
        model = getattr(settings, f"{name}_model")
        if key and model and model.strip():
            result.append(name)
        elif key:
            logger.warning("Provedor %s ignorado: modelo não configurado.", name)
    return result


class ProviderRouter:
    """Usa apenas falhas de provedor para failover; erros locais continuam visíveis."""

    def __init__(self, providers, *, timeout_seconds=12, budget_seconds=40,
                 cooldown_seconds=60, clock=time.monotonic,
                 analytical_timeouts: Mapping[str, float] | None = None):
        self.providers = list(providers)
        self.timeout_seconds = timeout_seconds
        self.analytical_timeouts = dict(analytical_timeouts or {})
        self.budget_seconds = budget_seconds
        self.cooldown_seconds = cooldown_seconds
        self.clock = clock
        self._health = {name: _Health() for name, _ in self.providers}
        self._lock = Lock()
        self._question: ContextVar[_Question | None] = ContextVar(
            f"provider_question_{id(self)}", default=None,
        )

    @contextmanager
    def question_scope(self):
        """Saldo e provedor preferido vivem só durante esta pergunta, inclusive insights."""
        token = self._question.set(_Question(self.budget_seconds))
        try:
            yield
        finally:
            self._question.reset(token)

    def complete(self, messages, tools):
        return self.complete_for_complexity(messages, tools, QuestionComplexity.SIMPLE)

    @property
    def selected_provider(self):
        question = self._question.get()
        return question.preferred if question else None

    def complete_for_complexity(self, messages, tools, complexity):
        if self._question.get() is None:
            with self.question_scope():
                return self.complete_for_complexity(messages, tools, complexity)
        question = self._question.get()
        providers = sorted(self.providers, key=lambda item: item[0] != question.preferred)
        for name, model in providers:
            if question.remaining <= 0:
                break
            revision = self._claim(name)
            if revision is None:
                continue
            started = self.clock()
            failed = False
            try:
                attempt_timeout = (
                    self.timeout_seconds if complexity == QuestionComplexity.SIMPLE
                    else self.analytical_timeouts.get(name, self.timeout_seconds)
                )
                result = model.complete_for_complexity(
                    messages, tools, complexity,
                    timeout_seconds=min(attempt_timeout, question.remaining),
                )
                self._validate_turn(result, tools)
                question.preferred = name
                self._success(name, revision)
                logger.info("Provedor %s modelo %s respondeu em %.2fs.",
                            name, model.model, self.clock() - started)
                return result
            except Exception as exc:
                kind = self._failure_kind(exc)
                if kind is None:
                    raise
                failed = True
                self._failure(name, permanent=kind == "credentials")
                logger.warning("Provedor %s modelo %s falhou (%s) após %.2fs.",
                               name, model.model, kind, self.clock() - started)
            finally:
                question.remaining -= max(0, self.clock() - started)
                if not failed:
                    with self._lock:
                        if self._health[name].revision == revision:
                            self._health[name].probing = False
        raise ProviderTransientError(
            "Os provedores de IA estão temporariamente indisponíveis. Tente novamente em breve."
        )

    @staticmethod
    def _validate_turn(result, tools):
        if not isinstance(result, ModelTurn):
            raise ProviderTransientError("Resposta do modelo inválida.")
        if result.tool_call is None:
            if not isinstance(result.answer, str) or not result.answer.strip():
                raise ProviderTransientError("Resposta do modelo vazia.")
            return
        call = result.tool_call
        if call.name not in {tool.name for tool in tools} or not isinstance(call.arguments, dict):
            raise ProviderTransientError("Chamada de ferramenta inválida.")
        if call.name == "run_sql" and (
            not isinstance(call.arguments.get("sql"), str) or not call.arguments["sql"].strip()
        ):
            raise ProviderTransientError("Argumentos da ferramenta inválidos.")

    def _claim(self, name):
        with self._lock:
            health = self._health[name]
            if health.disabled or health.probing or self.clock() < health.retry_after:
                return None
            if health.failed:
                health.probing = True
            return health.revision

    def _success(self, name, revision):
        with self._lock:
            if self._health[name].revision == revision:
                self._health[name] = _Health(revision=revision)

    def _failure(self, name, *, permanent):
        with self._lock:
            previous = self._health[name]
            if previous.disabled:
                return
            self._health[name] = _Health(
                revision=previous.revision + 1,
                retry_after=self.clock() + self.cooldown_seconds,
                failed=True, disabled=permanent,
            )

    @staticmethod
    def _failure_kind(exc):
        if isinstance(exc, (ProviderTransientError, TimeoutError, ConnectionError,
                            OSError, httpx.TransportError)):
            return "transient"
        status = (exc.response.status_code if isinstance(exc, httpx.HTTPStatusError)
                  else getattr(exc, "status_code", getattr(exc, "code", None)))
        try:
            status = int(status)
        except (TypeError, ValueError):
            return None
        provider_message = str(getattr(exc, "message", "")).lower()
        if status == 400 and "api key not valid" in provider_message:
            return "credentials"
        if status in {401, 403}:
            return "credentials"
        if status in {408, 429} or 500 <= status <= 599:
            return "transient"
        return None


def build_provider_router(settings):
    """Constrói clientes somente para as rotas explicitamente configuradas."""
    from app.gemini_adapter import GeminiToolCallingModel
    from app.openai_adapter import OpenAICompatibleModel

    providers = []
    for name in configured_providers(settings):
        key = getattr(settings, f"{name}_api_key").get_secret_value().strip()
        if name == "gemini":
            model = GeminiToolCallingModel(
                key, model=settings.gemini_model,
                complex_model=settings.gemini_complex_model,
                fallback_model=settings.gemini_fallback_model,
            )
        else:
            model = OpenAICompatibleModel(name, key, getattr(settings, f"{name}_model").strip())
        providers.append((name, model))
    return ProviderRouter(
        providers, timeout_seconds=settings.provider_timeout_seconds,
        budget_seconds=settings.provider_budget_seconds,
        cooldown_seconds=settings.provider_cooldown_seconds,
        analytical_timeouts={
            "gemini": max(settings.provider_timeout_seconds,
                          settings.gemini_analytical_timeout_seconds),
            "openrouter": max(settings.provider_timeout_seconds,
                              settings.openrouter_analytical_timeout_seconds),
        },
    )
