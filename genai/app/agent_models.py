"""Tipos internos para o contrato de tool calling do agente."""

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ToolDefinition:
    """Descrição mínima enviada a um modelo compatível com tool calling."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """Pedido de execução produzido pelo modelo."""

    name: str
    arguments: dict[str, Any]
    thought_signature: bytes | None = None


@dataclass(frozen=True)
class ModelTurn:
    """Turno normalizado de um adaptador de modelo."""

    answer: str | None = None
    tool_call: ToolCall | None = None


@dataclass(frozen=True)
class AgentResponse:
    """Resposta factual produzida após uma ferramenta retornar dados."""

    answer: str
    rows: tuple[dict[str, Any], ...]
    truncated: bool
    tool_calls: int
    columns: tuple[str, ...] = ()
    query_id: str | None = None
    metric: str | None = None
    unit: str | None = None
    period: str | None = None
    population: str | None = None
    limitations: str | None = None
    source: Literal["gold", "platform", "mixed"] = "gold"
    insights: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConversationContext:
    """Resumo mínimo de uma pergunta anterior enviado pela sessão atual."""

    question: str
    metric: str | None = None
    unit: str | None = None
    period: str | None = None
    population: str | None = None


ToolName = Literal["run_sql"]
