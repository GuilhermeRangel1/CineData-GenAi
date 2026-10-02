"""Gera os resultados esperados das consultas obrigatórias no Gold."""

from pathlib import Path

from app.evaluation_cases import MANDATORY_EVALUATIONS
from app.evaluation_runner import generate_snapshot

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    generate_snapshot(
        database_path=ROOT / "data" / "cinerocket.db",
        reference_sql_path=ROOT / "docs" / "genai" / "reference-queries.sql",
        output_path=ROOT / "docs" / "genai" / "reference-results.json",
        cases=MANDATORY_EVALUATIONS,
    )
    print("Snapshot de resultados Gold gerado em docs/genai/reference-results.json")


if __name__ == "__main__":
    main()
