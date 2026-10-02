"""Verifica o catálogo local das perguntas obrigatórias."""

import pytest

from app.evaluation_cases import (
    MANDATORY_EVALUATIONS,
    find_evaluation_case,
    get_evaluation_case,
)


def test_catalog_contains_all_reference_queries_once() -> None:
    query_ids = [case.query_id for case in MANDATORY_EVALUATIONS]

    assert query_ids == [f"Q{number:02d}" for number in range(1, 15)]
    assert len(query_ids) == len(set(query_ids))


@pytest.mark.parametrize("case", MANDATORY_EVALUATIONS, ids=lambda case: case.query_id)
def test_case_has_question_and_expected_columns(case) -> None:
    assert case.question.strip()
    assert case.expected_columns
    assert all(column.strip() for column in case.expected_columns)
    assert get_evaluation_case(case.query_id) == case


def test_unknown_case_is_rejected() -> None:
    with pytest.raises(KeyError, match="desconhecido"):
        get_evaluation_case("Q99")


def test_find_evaluation_case_normalizes_whitespace_and_case() -> None:
    case = find_evaluation_case("  QUAIS SÃO OS 10 FILMES COM MAIOR RECEITA EM BRL?  ")

    assert case is not None
    assert case.query_id == "Q01"


def test_find_evaluation_case_returns_none_for_free_question() -> None:
    assert find_evaluation_case("Mostre uma análise livre do catálogo") is None


@pytest.mark.parametrize("query_id", tuple(f"Q{number:02d}" for number in range(1, 15)))
def test_first_metric_groups_have_semantic_response_contract(query_id: str) -> None:
    case = get_evaluation_case(query_id)

    assert case.metric
    assert case.unit
    assert case.period
    assert case.population
    assert case.limitations
