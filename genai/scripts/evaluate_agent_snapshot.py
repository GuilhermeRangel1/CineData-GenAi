"""Reproduz o ciclo do agente para cada consulta de referência sem rede."""

import json
import time
from pathlib import Path

from app.agent import AgentService
from app.agent_models import ModelTurn, ToolCall
from app.evaluation_cases import MANDATORY_EVALUATIONS, EvaluationCase
from app.evaluation_runner import (
    assert_expected_columns,
    compare_rows,
    load_reference_queries,
)
from app.gold_database import GoldDatabase
from app.sql_executor import GoldQueryExecutor

ROOT = Path(__file__).resolve().parents[2]


class ReferenceModel:
    """Modelo simulado que devolve o SQL de referência de cada caso."""

    def __init__(self, sql: str, case: EvaluationCase) -> None:
        self.turns = [
            ModelTurn(tool_call=ToolCall("run_sql", {"sql": sql})),
            ModelTurn(
                answer=(
                    "Resposta: Resultado validado localmente.\n"
                    f"Métrica: {case.metric}\n"
                    f"Unidade: {case.unit}\n"
                    f"Período: {case.period}\n"
                    f"População válida: {case.population}\n"
                    f"Limitações: {case.limitations}"
                )
            ),
        ]

    def complete(self, messages, tools):
        return self.turns.pop(0)


def main() -> None:
    snapshot = json.loads(
        (ROOT / "docs" / "genai" / "reference-results.json").read_text(encoding="utf-8")
    )
    queries = load_reference_queries(ROOT / "docs" / "genai" / "reference-queries.sql")
    database = GoldDatabase(ROOT / "data" / "cinerocket.db")
    executor = GoldQueryExecutor(
        database,
        timeout_seconds=5.0,
        complex_timeout_seconds=15.0,
        progress_steps=100_000,
    )
    started = time.perf_counter()

    for case in MANDATORY_EVALUATIONS:
        response = AgentService(ReferenceModel(queries[case.query_id], case), executor).answer(
            case.question
        )
        assert_expected_columns(response.rows, case.expected_columns)
        compare_rows(response.rows, snapshot["results"][case.query_id]["rows"])
        print(f"{case.query_id}: ok ({len(response.rows)} linhas)")

    print(f"Todas as avaliações passaram em {time.perf_counter() - started:.1f}s.")


if __name__ == "__main__":
    main()
