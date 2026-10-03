"""Contrato do catálogo ampliado de avaliações sem chamadas ao provedor."""

from app.evaluation_cases import get_evaluation_case
from app.evaluation_scenarios import EXPANDED_EVALUATIONS


def test_expanded_scenarios_cover_language_filters_edges_and_platform() -> None:
    outcomes = {scenario.outcome for scenario in EXPANDED_EVALUATIONS}
    names = {scenario.name for scenario in EXPANDED_EVALUATIONS}

    assert {"success", "clarification", "empty", "platform"} <= outcomes
    assert {"filtro_ano", "empate_receita", "resultado_vazio", "ambiguidade"} <= names


def test_reference_scenarios_target_known_gold_metrics() -> None:
    for scenario in EXPANDED_EVALUATIONS:
        if scenario.reference_query_id:
            assert get_evaluation_case(scenario.reference_query_id).expected_columns
