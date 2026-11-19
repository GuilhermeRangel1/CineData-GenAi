"""Avaliação opt-in com APIs reais; executar no ambiente configurado do GenAI."""

import argparse
import hashlib
import json
import logging
import time
from dataclasses import replace
from pathlib import Path

from app.api import get_agent_service
from app.config import get_settings
from app.errors import (
    ProviderConfigurationError,
    ProviderTransientError,
    QueryExecutionError,
    QueryTimeoutError,
    SqlValidationError,
)
from app.evaluation_cases import MANDATORY_EVALUATIONS
from app.evaluation_paraphrases import EVALUATION_PARAPHRASES
from app.evaluation_runner import (
    EvaluationMismatch,
    compare_rows,
    execute_reference_query,
    load_reference_queries,
)
from app.expansion_evaluation_cases import EXPANSION_EVALUATIONS

_TECHNICAL_IDS = {"sk_movie_id", "sk_person_id", "sk_director_id", "sk_company_id", "sk_genre_id"}
_EVALUATION_ALIASES = {
    "Q02": {
        "media_lucro_brl": "lucro_medio_brl",
        "qtd_filmes": "filmes_elegiveis",
        "total_filmes": "filmes_elegiveis",
    },
    "Q05": {"diferenca": "divergencia", "diferenca_notas": "divergencia", "diff": "divergencia"},
    "Q06": {
        "ano": "ano_lancamento",
        "media_nota_imdb": "nota_imdb_media",
        "qtd_filmes_avaliados": "filmes_validos",
        "qtd_filmes": "filmes_validos",
    },
    "Q08": {
        "media_nota_imdb": "nota_media",
        "media_imdb": "nota_media",
        "qtd_filmes": "filmes_validos",
    },
    "Q11": {"lucro_brl": "lucro_total_brl", "qtd_filmes": "filmes_elegiveis"},
    "Q12": {"total_filmes": "filmes_validos", "qtd_filmes": "filmes_validos"},
    "Q18": {"diff": "diferenca", "diferenca_notas": "diferenca"},
    "Q22": {
        "total_filmes": "filmes_elegiveis",
        "total_elegivel": "filmes_elegiveis",
        "percentual_lucrativos": "percentual_lucrativo",
        "percentual_lucro": "percentual_lucrativo",
        "qtd_lucro": "filmes_lucrativos",
        "total_lucrativos": "filmes_lucrativos",
    },
}


def comparable_rows(rows, expected_rows, *, case_id, optional_ids):
    """Preserve requested data and compare internal IDs only if required or shared."""
    actual_keys = set(rows[0]) if rows else set()
    expected_keys = set(expected_rows[0]) if expected_rows else set()
    ignored = _TECHNICAL_IDS & (
        actual_keys ^ expected_keys if optional_ids else actual_keys - expected_keys
    )
    aliases = _EVALUATION_ALIASES.get(case_id, {})
    actual = []
    for row in rows:
        renamed = {aliases.get(key, key): value for key, value in row.items() if key not in ignored}
        if len(renamed) != len(row.keys() - ignored):
            raise EvaluationMismatch("A consulta retornou a mesma métrica em mais de uma coluna.")
        actual.append(renamed)
    expected = [
        {key: value for key, value in row.items() if key not in ignored}
        for row in expected_rows
    ]
    return actual, expected


class RouteLog(logging.Handler):
    def __init__(self):
        super().__init__()
        self.events = []
        self.provider_events = []

    def emit(self, record):
        message = record.getMessage()
        if "query_source=" in message:
            self.events.append(message.rsplit("query_source=", 1)[1])
        if record.name == "app.provider_router" and message.startswith("Provedor "):
            self.provider_events.append(message)
        if record.name == "app.gemini_adapter" and message.startswith(
            ("Gemini respondeu", "Modelo Gemini")
        ):
            self.provider_events.append(message)


def failure_category(exc, provider_events):
    if isinstance(exc, ProviderConfigurationError):
        return "provider_configuration"
    if isinstance(exc, ProviderTransientError):
        return ("provider_credentials" if any("(credentials)" in event for event in provider_events)
                else "provider_unavailable")
    if isinstance(exc, QueryTimeoutError):
        return "sql_timeout"
    if isinstance(exc, (SqlValidationError, QueryExecutionError)) or isinstance(
        exc.__cause__, (SqlValidationError, QueryExecutionError)
    ):
        return "sql_error"
    if isinstance(exc, EvaluationMismatch) or isinstance(exc.__cause__, EvaluationMismatch):
        return "result_mismatch"
    return "agent_error"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-only", action="store_true")
    parser.add_argument("--reference", default="/tmp/reference-queries.sql")
    parser.add_argument("--expansion-reference", type=Path)
    parser.add_argument("--output", default="/tmp/live-provider-results.json")
    parser.add_argument("--cases", default="")
    parser.add_argument("--paraphrases", action="store_true")
    parser.add_argument("--providers", default="groq,openrouter")
    parser.add_argument("--interval", type=float, default=0)
    parser.add_argument(
        "--stop-on-rate-limit",
        action="store_true",
        help="Salva o resultado e encerra a rodada no primeiro HTTP 429.",
    )
    parser.add_argument("--novel", action="store_true")
    args = parser.parse_args()
    if args.novel and args.paraphrases:
        parser.error("--novel e --paraphrases não podem ser usados juntos.")
    settings = get_settings()
    queries = load_reference_queries(Path(args.reference))
    log = RouteLog()
    agent_log = logging.getLogger("app.agent")
    agent_log.setLevel(logging.INFO)
    agent_log.addHandler(log)
    for name in ("app.provider_router", "app.gemini_adapter"):
        provider_log = logging.getLogger(name)
        provider_log.setLevel(logging.INFO)
        provider_log.addHandler(log)
    report = []
    cases = MANDATORY_EVALUATIONS
    if args.expansion_reference:
        queries.update(load_reference_queries(args.expansion_reference))
        cases += EXPANSION_EVALUATIONS
    if args.novel:
        cases = (replace(cases[0], question="Liste os três filmes de maior receita em BRL."),)
    for case in cases:
        if args.cases and case.query_id not in args.cases.split(","):
            continue
        reference_sql = queries[case.query_id]
        if args.novel:
            reference_sql = reference_sql.replace("LIMIT 10", "LIMIT 3")
        expected = execute_reference_query(settings.gold_database_path, reference_sql)
        if tuple(expected["columns"]) != case.expected_columns:
            raise ValueError(f"{case.query_id}: colunas da referência divergentes do catálogo.")
        for provider in args.providers.split(","):
            settings.provider_order = provider
            get_agent_service.cache_clear()
            service = get_agent_service()
            service.model_only = args.model_only
            service.insight_service = None
            sql_attempts = []
            proposed_sql = []
            provider_errors = []
            for _, adapter in service.model.providers:
                adapter_complete = adapter.complete_for_complexity

                def capture_provider_error(
                    *args, complete=adapter_complete, errors=provider_errors, **kwargs
                ):
                    try:
                        return complete(*args, **kwargs)
                    except Exception as exc:
                        response = getattr(exc, "response", None)
                        status = getattr(response, "status_code", None)
                        if status is None:
                            status = getattr(exc, "status_code", getattr(exc, "code", None))
                        error = {
                            "type": type(exc).__name__,
                            "status": str(status) if status else None,
                        }
                        if str(status) == "429" and response is not None:
                            retry_after = getattr(response, "headers", {}).get("retry-after", "")
                            if retry_after.isascii() and retry_after.isdecimal():
                                error["retry_after_seconds"] = int(retry_after)
                        errors.append(error)
                        raise

                adapter.complete_for_complexity = capture_provider_error
            execute = service.executor.execute
            def capture(query, execute=execute, sql_attempts=sql_attempts):
                sql_attempts.append(query.sql)
                return execute(query)
            service.executor.execute = capture
            complete = service.model.complete_for_complexity

            def capture_proposal(
                messages, tools, complexity, complete=complete, proposals=proposed_sql
            ):
                turn = complete(messages, tools, complexity)
                if turn.tool_call is not None:
                    sql = turn.tool_call.arguments.get("sql")
                    if isinstance(sql, str):
                        proposals.append(sql)
                return turn

            service.model.complete_for_complexity = capture_proposal
            log.events.clear()
            log.provider_events.clear()
            question = (
                EVALUATION_PARAPHRASES[case.query_id][0] if args.paraphrases else case.question
            )
            started = time.monotonic()
            entry = {"provider": provider, "model": getattr(settings, f"{provider}_model"),
                     "case": case.query_id, "question": question,
                     "formulation": "paraphrase" if args.paraphrases else "canonical",
                     "model_only": args.model_only,
                     "agent_sha256": hashlib.sha256(
                         Path(__import__("app.agent", fromlist=["__file__"]).__file__).read_bytes()
                     ).hexdigest()}
            try:
                with service.model.question_scope():
                    response = service.answer(question)
                    entry["selected_provider"] = service.model.selected_provider
                entry.update(answer=response.answer, rows=len(response.rows),
                             returned_columns=list(response.columns))
                if not log.events:
                    raise EvaluationMismatch("O agente não executou uma consulta analítica.")
                rows = response.rows
                reference_rows = expected["rows"]
                if args.paraphrases or case in EXPANSION_EVALUATIONS:
                    rows, reference_rows = comparable_rows(
                        rows, reference_rows, case_id=case.query_id, optional_ids=args.paraphrases,
                    )
                compare_rows(rows, reference_rows)
                entry["status"] = "passed"
            except Exception as exc:
                entry.update(status="failed", error_type=type(exc).__name__, error=str(exc),
                             failure_category=failure_category(exc, log.provider_events))
            entry["query_source"] = log.events[-1:]
            entry["direct_hit"] = entry["status"] == "passed" and entry["query_source"] == ["model"]
            entry["provider_events"] = log.provider_events.copy()
            entry["provider_errors"] = provider_errors
            entry["proposed_sql"] = proposed_sql
            entry["sql_attempts"] = sql_attempts
            entry["seconds"] = round(time.monotonic() - started, 2)
            report.append(entry)
            Path(args.output).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            print(json.dumps(entry, ensure_ascii=False), flush=True)
            rate_limited = any(error["status"] == "429" for error in provider_errors)
            if args.stop_on_rate_limit and rate_limited:
                return
            time.sleep(max(0, args.interval))


if __name__ == "__main__":
    main()
