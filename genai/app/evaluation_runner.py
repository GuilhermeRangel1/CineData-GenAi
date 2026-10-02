"""Execução local das consultas de referência para gerar expectativas do Gold."""

import hashlib
import json
import math
import re
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from app.evaluation_cases import EvaluationCase

_QUERY_HEADER = re.compile(r"^--\s*(Q\d+):", re.MULTILINE)


class EvaluationMismatch(ValueError):
    """Resultado do agente diferente da expectativa derivada do Gold."""


def load_reference_queries(path: Path) -> dict[str, str]:
    """Lê as consultas Q01–Q14 do arquivo SQL versionado."""

    text = path.read_text(encoding="utf-8")
    matches = list(_QUERY_HEADER.finditer(text))
    queries: dict[str, str] = {}
    for index, match in enumerate(matches):
        query_id = match.group(1)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        lines = text[match.end() : end].splitlines()[1:]
        sql = "\n".join(line for line in lines if not line.lstrip().startswith("--")).strip()
        sql = sql.rstrip(";").strip()
        if not sql:
            raise ValueError(f"A consulta {query_id} está vazia.")
        if query_id in queries:
            raise ValueError(f"A consulta {query_id} está duplicada.")
        queries[query_id] = sql
    return queries


def execute_reference_query(database_path: Path, sql: str) -> dict[str, Any]:
    """Executa uma consulta de referência usando uma conexão SQLite read-only."""

    resolved_path = database_path.expanduser().resolve()
    uri = f"file:{resolved_path.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("PRAGMA query_only = ON")
        cursor = connection.execute(sql)
        columns = tuple(description[0] for description in cursor.description or ())
        rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    return {"columns": list(columns), "row_count": len(rows), "rows": rows}


def compare_rows(
    actual_rows: Sequence[Mapping[str, Any]],
    expected_rows: Sequence[Mapping[str, Any]],
    *,
    absolute_tolerance: float = 0.01,
) -> None:
    """Compara valores tabulares sem exigir igualdade textual do SQL."""

    if len(actual_rows) != len(expected_rows):
        raise EvaluationMismatch(
            f"Quantidade de linhas divergente: esperado {len(expected_rows)}, "
            f"recebido {len(actual_rows)}."
        )

    for row_index, (actual, expected) in enumerate(zip(actual_rows, expected_rows, strict=True)):
        expected_keys = tuple(expected)
        actual_values = (
            tuple(actual[key] for key in expected_keys)
            if all(key in actual for key in expected_keys)
            else tuple(actual.values())
        )
        expected_values = tuple(expected.values())
        if len(actual_values) != len(expected_values):
            raise EvaluationMismatch(f"Quantidade de colunas divergente na linha {row_index}.")

        for column_index, (actual_value, expected_value) in enumerate(
            zip(actual_values, expected_values, strict=True)
        ):
            if isinstance(actual_value, (int, float)) and isinstance(expected_value, (int, float)):
                if not math.isclose(
                    float(actual_value),
                    float(expected_value),
                    rel_tol=1e-9,
                    abs_tol=absolute_tolerance,
                ):
                    raise EvaluationMismatch(
                        f"Valor divergente na linha {row_index}, coluna {column_index}: "
                        f"esperado {expected_value!r}, recebido {actual_value!r}."
                    )
            elif actual_value != expected_value:
                raise EvaluationMismatch(
                    f"Valor divergente na linha {row_index}, coluna {column_index}: "
                    f"esperado {expected_value!r}, recebido {actual_value!r}."
                )


def generate_snapshot(
    database_path: Path,
    reference_sql_path: Path,
    output_path: Path,
    cases: tuple[EvaluationCase, ...],
) -> None:
    """Gera um snapshot determinístico dos resultados esperados no Gold atual."""

    queries = load_reference_queries(reference_sql_path)
    expected_ids = {case.query_id for case in cases}
    if set(queries) != expected_ids:
        raise ValueError("As consultas de referência não correspondem aos casos obrigatórios.")

    results: dict[str, dict[str, Any]] = {}
    for case in cases:
        result = execute_reference_query(database_path, queries[case.query_id])
        if tuple(result["columns"]) != case.expected_columns:
            raise ValueError(
                f"As colunas de {case.query_id} não correspondem ao catálogo: {result['columns']}"
            )
        results[case.query_id] = result

    snapshot = {
        "snapshot_version": 1,
        "gold": {
            "size_bytes": database_path.stat().st_size,
            "sha256": hashlib.sha256(database_path.read_bytes()).hexdigest(),
        },
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
