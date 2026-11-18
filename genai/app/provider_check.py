"""Smoke test opt-in de tool calling real, sem cache nem SQL de referência do agente."""

import argparse
import json
import logging
import time

from app.agent_models import ToolDefinition
from app.config import Settings, get_settings
from app.gold_database import GoldDatabase
from app.provider_router import build_provider_router, configured_providers
from app.sql_executor import GoldQueryExecutor
from app.sql_guard import validate_sql


class _SimulatedFailure:
    model = "simulated-unavailable"

    def complete_for_complexity(self, *args, **kwargs):
        raise TimeoutError("Falha local simulada")


def check_provider_chain(settings: Settings, order: str, simulate_failure: list[str]) -> dict:
    """Exige todas as rotas solicitadas e confere a resposta do modelo contra o Gold."""
    # model_copy não valida atualizações; reconstruir mantém validação de ordem/limites.
    settings = Settings(_env_file=None, **{**settings.model_dump(), "provider_order": order})
    names = settings.provider_order.split(",")
    available = configured_providers(settings)
    missing = set(names) - set(available)
    if missing:
        raise ValueError("Provedores sem chave/modelo: " + ", ".join(sorted(missing)))
    if set(simulate_failure) - set(names):
        raise ValueError("Falha simulada precisa pertencer à ordem solicitada.")
    router = build_provider_router(settings)
    router.providers = [
        (name, _SimulatedFailure() if name in simulate_failure else model)
        for name, model in router.providers
    ]
    database = GoldDatabase(settings.gold_database_path, settings.gold_timeout_seconds)
    executor = GoldQueryExecutor(database, timeout_seconds=settings.gold_timeout_seconds)
    tool = ToolDefinition("run_sql", "Executa um SELECT somente leitura no Gold.", {
        "type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"],
    })
    started = time.monotonic()
    with router.question_scope():
        turn = router.complete([
            {"role": "system", "content": (
                "Use run_sql para responder. O catálogo SQLite contém a tabela dim_movies; "
                "cada linha é um filme. Retorne uma contagem sem filtros com alias total."
            )},
            {"role": "user", "content": "Quantos filmes existem no catálogo?"},
        ], [tool])
        provider = router.selected_provider
    if turn.tool_call is None or turn.tool_call.name != "run_sql":
        raise ValueError("O modelo não produziu o tool call esperado.")
    sql = turn.tool_call.arguments.get("sql")
    if not isinstance(sql, str):
        raise ValueError("O modelo retornou argumentos inválidos.")
    actual = executor.execute(validate_sql(sql))
    expected = executor.execute(validate_sql("SELECT COUNT(*) AS total FROM dim_movies"))
    if actual.rows != expected.rows or actual.columns != expected.columns or actual.truncated:
        raise ValueError("A contagem produzida pelo modelo diverge da referência local.")
    return {
        "status": "success", "order": names, "simulated_failures": simulate_failure,
        "provider": provider, "configured_model": getattr(settings, f"{provider}_model"),
        "seconds": round(time.monotonic() - started, 3),
        "total_movies": actual.rows[0]["total"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--order", required=True, help="Ex.: groq ou gemini,groq,openrouter")
    parser.add_argument("--simulate-failure", action="append", default=[])
    args = parser.parse_args()
    # Evita logging HTTP detalhado que possa incluir respostas brutas de provedores.
    logging.basicConfig(level=logging.WARNING)
    try:
        report = check_provider_chain(get_settings(), args.order, args.simulate_failure)
    except Exception as exc:
        # Nunca exibir o corpo da exceção: SDKs podem incluir dados da requisição.
        response = getattr(exc, "response", None)
        safe_status = getattr(response, "status_code", None)
        if safe_status is None:
            safe_status = getattr(exc, "status_code", getattr(exc, "code", None))
        print(json.dumps({"status": "error", "error_type": type(exc).__name__,
                          "http_status": safe_status,
                          "message": "Verifique configuração, cota e logs seguros de rota."}))
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
