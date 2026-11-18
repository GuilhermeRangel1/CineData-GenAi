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
from app.evaluation_cases import MANDATORY_EVALUATIONS
from app.evaluation_runner import compare_rows, execute_reference_query, load_reference_queries


class RouteLog(logging.Handler):
    def __init__(self):
        super().__init__()
        self.events = []

    def emit(self, record):
        message = record.getMessage()
        if "query_source=" in message:
            self.events.append(message.rsplit("query_source=", 1)[1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-only", action="store_true")
    parser.add_argument("--reference", default="/tmp/reference-queries.sql")
    parser.add_argument("--output", default="/tmp/live-provider-results.json")
    parser.add_argument("--cases", default="")
    parser.add_argument("--paraphrases", action="store_true")
    parser.add_argument("--providers", default="groq,openrouter")
    parser.add_argument("--interval", type=float, default=0)
    parser.add_argument("--novel", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    queries = load_reference_queries(Path(args.reference))
    log = RouteLog()
    agent_log = logging.getLogger("app.agent")
    agent_log.setLevel(logging.INFO)
    agent_log.addHandler(log)
    report = []
    cases = MANDATORY_EVALUATIONS
    if args.novel:
        cases = (replace(cases[0], question="Liste os três filmes de maior receita em BRL."),)
    for case in cases:
        if args.cases and case.query_id not in args.cases.split(","):
            continue
        reference_sql = queries[case.query_id]
        if args.novel:
            reference_sql = reference_sql.replace("LIMIT 10", "LIMIT 3")
        expected = execute_reference_query(settings.gold_database_path, reference_sql)
        for provider in args.providers.split(","):
            settings.provider_order = provider
            get_agent_service.cache_clear()
            service = get_agent_service()
            service.model_only = args.model_only
            service.insight_service = None
            sql_attempts = []
            execute = service.executor.execute
            def capture(query, execute=execute, sql_attempts=sql_attempts):
                sql_attempts.append(query.sql)
                return execute(query)
            service.executor.execute = capture
            log.events.clear()
            question = case.question
            if args.paraphrases:
                question = {
                    "Q03": "Liste os dez títulos com maior margem de lucro por filme.",
                    "Q12": ("Qual categoria de gênero lidera a média das margens "
                            "individuais dos filmes?"),
                }.get(case.query_id, case.question)
            started = time.monotonic()
            entry = {"provider": provider, "model": getattr(settings, f"{provider}_model"),
                     "case": case.query_id, "question": question,
                     "model_only": args.model_only,
                     "agent_sha256": hashlib.sha256(
                         Path(__import__("app.agent", fromlist=["__file__"]).__file__).read_bytes()
                     ).hexdigest()}
            try:
                with service.model.question_scope():
                    response = service.answer(question)
                compare_rows(response.rows, expected["rows"])
                entry.update(status="passed", rows=len(response.rows),
                             insights=len(response.insights), query_source=log.events[-1:])
            except Exception as exc:
                entry.update(status="failed", error_type=type(exc).__name__, error=str(exc),
                             query_source=log.events[-1:])
            entry["sql_attempts"] = sql_attempts
            entry["seconds"] = round(time.monotonic() - started, 2)
            report.append(entry)
            Path(args.output).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            print(json.dumps(entry, ensure_ascii=False), flush=True)
            time.sleep(max(0, args.interval))


if __name__ == "__main__":
    main()
