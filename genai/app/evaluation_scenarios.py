"""Cenários locais além das formulações canônicas Q01–Q14."""

from dataclasses import dataclass
from typing import Literal


ExpectedOutcome = Literal["success", "clarification", "empty", "platform"]


@dataclass(frozen=True)
class EvaluationScenario:
    """Pergunta local e o comportamento verificável esperado do agente."""

    name: str
    question: str
    outcome: ExpectedOutcome
    reference_query_id: str | None = None
    notes: str = ""


EXPANDED_EVALUATIONS: tuple[EvaluationScenario, ...] = (
    EvaluationScenario("q01_reformulada", "Mostre os dez filmes com maior faturamento em BRL.", "success", "Q01"),
    EvaluationScenario("q04_reformulada", "Quais filmes lideram em popularidade?", "success", "Q04"),
    EvaluationScenario("q08_reformulada", "Quais diretores têm melhor média no IMDb com pelo menos cinco filmes?", "success", "Q08"),
    EvaluationScenario("q11_reformulada", "Qual produtora teve o maior lucro total em reais?", "success", "Q11"),
    EvaluationScenario("filtro_ano", "Qual produtora acumulou o maior lucro total em BRL em 2020?", "success", "Q11", "Compara a métrica, não o SQL textual."),
    EvaluationScenario("empate_receita", "Quais filmes empatam na maior receita?", "success", "Q01", "Preserva todos os empatados."),
    EvaluationScenario("resultado_vazio", "Quais filmes tiveram receita em BRL no ano de 1800?", "empty", notes="Não deve inventar resultados."),
    EvaluationScenario("ambiguidade", "Quais filmes tiveram melhor desempenho?", "clarification", notes="Métrica e critério são insuficientes."),
    EvaluationScenario("plataforma_catalogo", "Como uso os filtros de filmes no CineData?", "platform"),
    EvaluationScenario("plataforma_comunidades", "Como funciona a aba Comunidades?", "platform"),
)
