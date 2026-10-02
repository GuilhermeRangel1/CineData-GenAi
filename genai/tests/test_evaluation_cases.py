"""Verifica o catálogo local das perguntas obrigatórias."""

import pytest

from app.evaluation_cases import MANDATORY_EVALUATIONS, get_evaluation_case


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
