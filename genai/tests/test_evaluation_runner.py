"""Testes do parser e do contrato do snapshot de avaliações."""

import json
from pathlib import Path

import pytest

from app.evaluation_cases import MANDATORY_EVALUATIONS
from app.evaluation_runner import (
    EvaluationMismatch,
    assert_expected_columns,
    compare_rows,
    load_reference_queries,
)

ROOT = Path(__file__).resolve().parents[2]


def test_assert_expected_columns_accepts_case_contract() -> None:
    assert_expected_columns(
        ({"titulo": "A", "receita_brl": 10.0},),
        ("titulo", "receita_brl"),
    )


def test_assert_expected_columns_reports_missing_columns() -> None:
    with pytest.raises(EvaluationMismatch, match="receita_brl"):
        assert_expected_columns(({"titulo": "A"},), ("titulo", "receita_brl"))


def test_reference_queries_cover_all_cases() -> None:
    queries = load_reference_queries(ROOT / "docs" / "genai" / "reference-queries.sql")

    assert list(queries) == [case.query_id for case in MANDATORY_EVALUATIONS]
    assert all(query.lstrip().upper().startswith(("SELECT", "WITH")) for query in queries.values())


def test_reference_snapshot_matches_catalog() -> None:
    snapshot = json.loads(
        (ROOT / "docs" / "genai" / "reference-results.json").read_text(encoding="utf-8")
    )

    assert snapshot["snapshot_version"] == 1
    assert set(snapshot["results"]) == {case.query_id for case in MANDATORY_EVALUATIONS}
    for case in MANDATORY_EVALUATIONS:
        result = snapshot["results"][case.query_id]
        assert tuple(result["columns"]) == case.expected_columns
        assert result["row_count"] == len(result["rows"])


def test_compare_rows_accepts_numeric_tolerance() -> None:
    compare_rows(
        [{"value": 10.005}],
        [{"value": 10.0}],
    )


def test_compare_rows_rejects_different_values() -> None:
    with pytest.raises(EvaluationMismatch, match="Valor divergente"):
        compare_rows(
            [{"value": 11.0}],
            [{"value": 10.0}],
        )
