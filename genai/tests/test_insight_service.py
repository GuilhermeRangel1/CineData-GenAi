"""Testes do agente de insights sem acesso ao Gold ou ao provedor."""

from app.agent_models import AgentResponse, ModelTurn
from app.insight_service import InsightService


class FakeInsightModel:
    def __init__(self, answer: str | None) -> None:
        self.answer = answer
        self.calls = []

    def complete(self, messages, tools):
        self.calls.append((messages, tools))
        return ModelTurn(answer=self.answer)


def test_insight_service_uses_only_visible_result_data() -> None:
    model = FakeInsightModel("- Drama lidera o ranking.\n- Comedy aparece em segundo lugar.")
    response = AgentResponse(
        answer="A consulta retornou resultados.",
        rows=(
            {"sk_movie_id": "secret-id", "titulo": "Drama", "receita_brl": 100.0},
            {"sk_movie_id": "another-id", "titulo": "Comedy", "receita_brl": 90.0},
        ),
        truncated=False,
        tool_calls=1,
        columns=("sk_movie_id", "titulo", "receita_brl"),
        query_id="Q01",
        metric="receita por filme",
        unit="BRL",
        period="todo o Gold disponível",
    )

    insights = InsightService(model).generate(response)

    assert insights == ("Drama lidera o ranking.", "Comedy aparece em segundo lugar.")
    assert model.calls[0][1] == ()
    assert "sk_movie_id" not in model.calls[0][0][1]["content"]
    assert "secret-id" not in model.calls[0][0][1]["content"]
    assert "diferenca_primeiro_segundo" in model.calls[0][0][1]["content"]
    assert "participacao_lider_no_recorte" in model.calls[0][0][1]["content"]


def test_insight_service_skips_non_chartable_results() -> None:
    model = FakeInsightModel("- Não deveria ser chamado.")
    response = AgentResponse(
        answer="Resultado.",
        rows=({"ator": "A", "diretor": "D", "filmes_em_comum": 2},),
        truncated=False,
        tool_calls=1,
        columns=("ator", "diretor", "filmes_em_comum"),
        query_id="Q09",
    )

    assert InsightService(model).generate(response) == ()
    assert model.calls == []


def test_imdb_average_by_year_explains_small_samples_without_calling_model() -> None:
    model = FakeInsightModel("- Este texto não deve ser usado.")
    response = AgentResponse(
        answer="Resultado.",
        rows=(
            {"ano_lancamento": 2016, "filmes_validos": 9532, "nota_imdb_media": 6.333078},
            {"ano_lancamento": 2017, "filmes_validos": 10283, "nota_imdb_media": 6.345181},
            {"ano_lancamento": 2024, "filmes_validos": 1504, "nota_imdb_media": 6.142021},
            {"ano_lancamento": 2025, "filmes_validos": 2, "nota_imdb_media": 6.15},
            {"ano_lancamento": 2026, "filmes_validos": 1, "nota_imdb_media": 7.5},
        ),
        truncated=False,
        tool_calls=0,
        columns=("ano_lancamento", "filmes_validos", "nota_imdb_media"),
        query_id="Q06",
        metric="média IMDb por ano de lançamento",
        unit="pontuação em escala de 0 a 10",
    )

    insights = InsightService(model).generate(response)

    assert insights == (
        "2026 tem a maior média observada (7,50), mas reúne apenas 1 filme válido.",
        "Entre os anos com ao menos 100 filmes válidos, 2017 tem a maior média (6,35; 10.283 filmes).",
        "A menor média é a de 2024 (6,14; 1.504 filmes válidos).",
    )
    assert model.calls == []
