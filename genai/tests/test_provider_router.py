"""Fallback, cooldown e orçamento com relógio controlado."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import httpx
import pytest
from pydantic import ValidationError

from app.agent_models import ModelTurn, ToolCall, ToolDefinition
from app.complexity_router import QuestionComplexity
from app.config import Settings
from app.errors import ProviderTransientError
from app.provider_router import ProviderRouter, configured_providers


class Clock:
    value = 0.0

    def __call__(self):
        return self.value


class Model:
    model = "test-model"

    def __init__(self, responses, clock=None, cost=0):
        self.responses = list(responses)
        self.calls = []
        self.clock = clock
        self.cost = cost

    def complete_for_complexity(self, messages, tools, complexity, *, timeout_seconds):
        self.calls.append(timeout_seconds)
        if self.clock:
            self.clock.value += self.cost
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return ModelTurn(answer=response)


def http_error(status):
    response = httpx.Response(status, request=httpx.Request("POST", "https://example.com"))
    return httpx.HTTPStatusError("do not log secrets", request=response.request, response=response)


def test_order_cooldown_and_recovery():
    clock = Clock()
    primary = Model([TimeoutError(), "recovered"])
    backup = Model(["backup", "backup again"])
    router = ProviderRouter([("gemini", primary), ("groq", backup)], clock=clock)
    assert router.complete([], []).answer == "backup"
    assert router.complete([], []).answer == "backup again"
    assert len(primary.calls) == 1
    clock.value = 61
    assert router.complete([], []).answer == "recovered"


@pytest.mark.parametrize("status", [401, 403])
def test_bad_credentials_disabled_until_restart(status):
    clock = Clock()
    primary = Model([http_error(status)])
    backup = Model(["ok", "ok"])
    router = ProviderRouter([("gemini", primary), ("groq", backup)], clock=clock)
    router.complete([], [])
    clock.value = 9999
    router.complete([], [])
    assert len(primary.calls) == 1


def test_google_sdk_invalid_key_400_is_classified_as_credentials():
    class GoogleAuthError(Exception):
        code = 400
        message = "API key not valid. Please pass a valid API key."

    router = ProviderRouter([("a", Model([GoogleAuthError()])), ("b", Model(["ok"]))])
    assert router.complete([], []).answer == "ok"
    assert router._health["a"].disabled


@pytest.mark.parametrize("failure", [http_error(429), http_error(503),
                                        ProviderTransientError("invalid"), ConnectionError()])
def test_fallback_on_expected_failures(failure):
    router = ProviderRouter([("a", Model([failure])), ("b", Model(["ok"]))])
    assert router.complete([], []).answer == "ok"


def test_programming_errors_do_not_trigger_fallback():
    backup = Model(["not expected"])
    router = ProviderRouter([("a", Model([ValueError("bug")])), ("b", backup)])
    with pytest.raises(ValueError):
        router.complete([], [])
    assert backup.calls == []


@pytest.mark.parametrize("turn", [ModelTurn(answer=" "),
    ModelTurn(tool_call=ToolCall("run_sql", {})),
    ModelTurn(tool_call=ToolCall("unknown", {"sql": "SELECT 1"})),
])
def test_router_rejects_invalid_turn_from_any_provider(turn):
    class InvalidModel:
        model = "test"

        def complete_for_complexity(self, *args, **kwargs):
            return turn

    router = ProviderRouter([("gemini", InvalidModel()), ("groq", Model(["backup"]))])
    tools = [ToolDefinition("run_sql", "Consulta", {"type": "object"})]
    assert router.complete([], tools).answer == "backup"


def test_total_failure_has_safe_error_without_underlying_secret():
    router = ProviderRouter([("a", Model([http_error(401)]))])
    with pytest.raises(ProviderTransientError, match="temporariamente") as caught:
        router.complete([], [])
    assert "secret" not in str(caught.value)


def test_shared_budget_and_preferred_route_only_within_question():
    clock = Clock()
    primary = Model([TimeoutError(), "primary"], clock, 8)
    backup = Model(["first", "insights"], clock, 7)
    router = ProviderRouter([("a", primary), ("b", backup)],
                            clock=clock, budget_seconds=20, cooldown_seconds=1)
    with router.question_scope():
        assert router.complete([], []).answer == "first"
        assert router.complete([], []).answer == "insights"
        assert backup.calls == [12, 5]
        with pytest.raises(ProviderTransientError):
            router.complete([], [])
    clock.value += 2
    assert router.complete([], []).answer == "primary"


def test_sql_time_is_not_inference_time_and_expired_insights_preserve_data():
    from app.agent_models import AgentResponse
    from app.insight_service import InsightService

    clock = Clock()
    model = Model(["first", "second"], clock, 2)
    router = ProviderRouter([("a", model)], clock=clock, budget_seconds=4)
    response = AgentResponse(
        answer="Dados prontos", rows=({"titulo": "A", "receita_brl": 2},
                                     {"titulo": "B", "receita_brl": 1}),
        truncated=False, tool_calls=1, query_id="Q01",
        columns=("titulo", "receita_brl"),
    )
    with router.question_scope():
        router.complete([], [])
        clock.value += 100  # Consulta local não deve consumir o orçamento de inferência.
        router.complete([], [])
        assert model.calls == [4, 2]
        assert InsightService(router).generate(response) == ()
        assert response.answer == "Dados prontos"
        assert len(response.rows) == 2
        assert len(model.calls) == 2


def test_openrouter_analytical_timeout_respects_question_budget():
    clock = Clock()
    primary = Model([TimeoutError()], clock, 10)
    openrouter = Model(["analytical", "simple"])
    router = ProviderRouter(
        [("groq", primary), ("openrouter", openrouter)],
        clock=clock,
        timeout_seconds=12,
        budget_seconds=30,
        analytical_timeouts={"openrouter": 22},
    )

    assert router.complete_for_complexity([], [], QuestionComplexity.ANALYTICAL).answer == (
        "analytical"
    )
    assert router.complete([], []).answer == "simple"
    assert primary.calls == [12]
    assert openrouter.calls == [20, 12]


def test_scope_budget_isolated_between_threads():
    barrier = Barrier(2)

    class ConcurrentModel:
        model = "test"

        def complete_for_complexity(self, *args, timeout_seconds):
            barrier.wait(timeout=3)
            assert timeout_seconds == 12
            return ModelTurn(answer="ok")

    router = ProviderRouter([("a", ConcurrentModel())])

    def question(_):
        with router.question_scope():
            return router.complete([], []).answer

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(question, range(2))) == ["ok", "ok"]


def test_concurrent_success_does_not_reenable_rejected_credentials():
    entered, release = Event(), Event()

    class ConcurrentModel:
        model = "test"
        calls = 0

        def complete_for_complexity(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                entered.set()
                assert release.wait(3)
                return ModelTurn(answer="late success")
            raise http_error(401)

    primary = ConcurrentModel()
    backup = Model(["backup", "still backup"])
    router = ProviderRouter([("a", primary), ("b", backup)])
    with ThreadPoolExecutor(max_workers=1) as pool:
        late = pool.submit(router.complete, [], [])
        assert entered.wait(3)
        try:
            assert router.complete([], []).answer == "backup"
        finally:
            release.set()
        assert late.result(timeout=3).answer == "late success"
    assert router.complete([], []).answer == "still backup"
    assert primary.calls == 2


def test_only_one_recovery_probe_runs_concurrently():
    clock = Clock()
    entered, release = Event(), Event()

    class RecoveringModel(Model):
        def complete_for_complexity(self, *args, **kwargs):
            if self.calls:
                entered.set()
                assert release.wait(3)
            return super().complete_for_complexity(*args, **kwargs)

    primary = RecoveringModel([TimeoutError(), "recovered"])
    backup = Model(["backup", "during probe"])
    router = ProviderRouter([("a", primary), ("b", backup)], clock=clock)
    router.complete([], [])
    clock.value = 61
    with ThreadPoolExecutor(max_workers=1) as pool:
        probe = pool.submit(router.complete, [], [])
        assert entered.wait(3)
        try:
            assert router.complete([], []).answer == "during probe"
        finally:
            release.set()
        assert probe.result(timeout=3).answer == "recovered"


def test_configuration_requires_key_and_model_and_honors_order():
    settings = Settings(_env_file=None, gemini_api_key="", groq_api_key="key",
                        groq_model="chosen", openrouter_api_key="key",
                        provider_order="groq,gemini,openrouter")
    assert configured_providers(settings) == ["groq"]


@pytest.mark.parametrize("order", ["groq,groq", "unknown", ""])
def test_invalid_provider_order(order):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, provider_order=order)


@pytest.mark.parametrize("field", ["provider_timeout_seconds", "provider_budget_seconds",
                                   "provider_cooldown_seconds"])
def test_positive_limits(field):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: 0})
