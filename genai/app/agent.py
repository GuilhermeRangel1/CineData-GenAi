"""Orquestração do agente sem acoplar um provedor específico."""

import json
from collections.abc import Sequence
from typing import Any, Protocol

from app.agent_models import AgentResponse, ModelTurn, ToolCall, ToolDefinition
from app.errors import QueryExecutionError, SqlValidationError
from app.evaluation_cases import MANDATORY_EVALUATIONS
from app.gold_database import EXPECTED_TABLES
from app.sql_executor import GoldQueryExecutor
from app.sql_guard import validate_sql


class AgentError(RuntimeError):
    """Falha controlada no ciclo de tool calling."""


class ToolCallingModel(Protocol):
    """Porta que qualquer framework/provedor de tool calling deve implementar."""

    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[ToolDefinition],
    ) -> ModelTurn:
        """Produz um turno de modelo a partir das mensagens e ferramentas."""


RUN_SQL_TOOL = ToolDefinition(
    name="run_sql",
    description="Executa uma consulta SELECT somente leitura nas tabelas Gold permitidas.",
    parameters={
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "Uma única consulta SELECT em SQLite sobre a camada Gold.",
            }
        },
        "required": ["sql"],
        "additionalProperties": False,
    },
)

_GOLD_TABLES_CONTEXT = ", ".join(sorted(EXPECTED_TABLES))
_MANDATORY_QUESTIONS_CONTEXT = "\n".join(
    f"{case.query_id}: {case.question} Colunas esperadas: {', '.join(case.expected_columns)}."
    for case in MANDATORY_EVALUATIONS
)


class AgentService:
    """Executa no máximo um tool call e pede ao modelo uma resposta final."""

    def __init__(self, model: ToolCallingModel, executor: GoldQueryExecutor, max_rows: int = 100):
        self.model = model
        self.executor = executor
        self.max_rows = max_rows

    def answer(self, question: str) -> AgentResponse:
        """Responde usando dados retornados pela ferramenta SQL controlada."""

        normalized_question = question.strip()
        if not normalized_question:
            raise AgentError("A pergunta não pode ser vazia.")

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "Responda em português. Para perguntas sobre o catálogo, "
                    "use exatamente a ferramenta run_sql. Não invente números. "
                    "Use somente estes nomes exatos de tabelas Gold: "
                    f"{_GOLD_TABLES_CONTEXT}. Não invente nomes de tabelas."
                    "\nIdentifique a intenção entre os casos obrigatórios abaixo e use "
                    "aliases iguais às colunas esperadas quando fizer sentido:\n"
                    f"{_MANDATORY_QUESTIONS_CONTEXT}"
                ),
            },
            {"role": "user", "content": normalized_question},
        ]
        first_turn = self.model.complete(messages, (RUN_SQL_TOOL,))
        call = self._require_tool_call(first_turn)
        if call.name != RUN_SQL_TOOL.name:
            raise AgentError("O modelo solicitou uma ferramenta não permitida.")

        query = call.arguments.get("sql")
        if not isinstance(query, str):
            raise AgentError("A ferramenta recebeu argumentos inválidos.")

        try:
            validated = validate_sql(query, max_rows=self.max_rows)
            result = self.executor.execute(validated)
        except (SqlValidationError, QueryExecutionError) as exc:
            raise AgentError("A consulta solicitada não pôde ser executada.") from exc

        messages.extend(
            [
                {
                    "role": "assistant",
                    "tool_call": {
                        "name": call.name,
                        "arguments": call.arguments,
                        "thought_signature": call.thought_signature,
                    },
                },
                {
                    "role": "tool",
                    "name": call.name,
                    "content": json.dumps(
                        {
                            "columns": result.columns,
                            "rows": result.rows,
                            "truncated": result.truncated,
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                },
            ]
        )
        final_turn = self.model.complete(messages, (RUN_SQL_TOOL,))
        if final_turn.tool_call is not None:
            raise AgentError("O modelo solicitou mais de uma consulta nesta pergunta.")
        if not final_turn.answer or not final_turn.answer.strip():
            raise AgentError("O modelo não produziu uma resposta final.")

        return AgentResponse(
            answer=final_turn.answer.strip(),
            rows=result.rows,
            truncated=result.truncated,
            tool_calls=1,
        )

    @staticmethod
    def _require_tool_call(turn: ModelTurn) -> ToolCall:
        if turn.tool_call is None:
            raise AgentError("O modelo não solicitou a ferramenta de consulta.")
        return turn.tool_call
