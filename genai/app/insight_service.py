"""Gera observações curtas a partir de resultados analíticos já aprovados."""

import json
import logging
import re
from collections.abc import Sequence
from typing import Any, Protocol

from app.agent_models import AgentResponse, ModelTurn, ToolDefinition


logger = logging.getLogger(__name__)

_CHARTABLE_CASES = frozenset({"Q01", "Q02", "Q03", "Q04", "Q05", "Q06", "Q07", "Q08", "Q10", "Q11", "Q12", "Q13", "Q14"})
_ID_COLUMN = re.compile(r"^(?:id|id_.*|.*_id)$", re.IGNORECASE)
_INSIGHT_COLUMNS = {
    "Q01": ("titulo", "receita_brl"),
    "Q02": ("nome_genero", "lucro_medio_brl"),
    "Q03": ("titulo", "margem"),
    "Q04": ("titulo", "popularidade"),
    "Q05": ("titulo", "divergencia"),
    "Q06": ("ano_lancamento", "nota_imdb_media"),
    "Q07": ("nome_pessoa", "total_filmes"),
    "Q08": ("nome_pessoa", "nota_media"),
    "Q10": ("nome_genero", "total_filmes"),
    "Q11": ("nome_produtora", "lucro_total_brl"),
    "Q12": ("nome_genero", "margem_media"),
    "Q13": ("titulo", "qtd_avaliacoes_usuarios"),
    "Q14": ("titulo", "divergencia"),
}


class InsightModel(Protocol):
    """Porta mínima para uma chamada textual sem ferramenta."""

    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[ToolDefinition],
    ) -> ModelTurn:
        """Retorna texto para o resumo dos dados recebidos."""


class InsightService:
    """Isola insights do agente SQL para que não possam consultar o Gold."""

    def __init__(self, model: InsightModel, max_insights: int = 3) -> None:
        self.model = model
        self.max_insights = max_insights

    def generate(self, response: AgentResponse) -> tuple[str, ...]:
        """Cria observações somente quando há dados suficientes para um gráfico."""

        if not self._is_chartable(response):
            return ()
        rows = self._visible_rows(response)
        if len(rows) < 2:
            return ()
        messages = (
            {
                "role": "system",
                "content": (
                    "Você é um analista de dados do CineData. Use exclusivamente os dados "
                    "recebidos nesta mensagem. Não faça consultas, não use conhecimento externo "
                    "e não invente números. Os sinais calculados são evidências prioritárias: use-os "
                    "para explicar diferenças relevantes, concentração, tendência, empates ou exceções. "
                    "Não apenas repita a primeira linha ou descreva o gráfico. Responda em português "
                    "com até três observações curtas, cada uma iniciada por '- '. Se os dados não "
                    "permitirem uma observação segura, responda somente com uma lista vazia."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "metrica": response.metric,
                        "unidade": response.unit,
                        "periodo": response.period,
                        "colunas": [column for column in response.columns if not _ID_COLUMN.match(column)],
                        "linhas": rows,
                        "sinais_calculados": self._derived_signals(response, rows),
                    },
                    ensure_ascii=False,
                ),
            },
        )
        try:
            turn = self.model.complete(messages, ())
        except Exception:  # The analytical answer remains useful if this optional call fails.
            logger.warning("Não foi possível gerar insights para a resposta GenAI.", exc_info=True)
            return ()
        return self._parse(turn.answer)

    @staticmethod
    def _is_chartable(response: AgentResponse) -> bool:
        return bool(
            response.query_id in _CHARTABLE_CASES
            or response.metric in {"quantidade de filmes por ator", "quantidade de filmes por produtora"}
        )

    @staticmethod
    def _visible_rows(response: AgentResponse) -> list[dict[str, Any]]:
        visible_columns = [column for column in response.columns if not _ID_COLUMN.match(column)]
        return [
            {column: row[column] for column in visible_columns if column in row}
            for row in response.rows[:8]
        ]

    @staticmethod
    def _derived_signals(
        response: AgentResponse, rows: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Calcula comparações explícitas que o modelo pode explicar sem inferir valores."""

        label_column, value_column = _INSIGHT_COLUMNS.get(
            response.query_id or "",
            ("nome_pessoa", "total_filmes"),
        )
        points = [
            (str(row[label_column]), float(row[value_column]))
            for row in rows
            if row.get(label_column) is not None and isinstance(row.get(value_column), (int, float))
        ]
        if len(points) < 2:
            return {}

        signals: dict[str, Any] = {
            "coluna_rotulo": label_column,
            "coluna_valor": value_column,
            "maior": {"rotulo": points[0][0], "valor": points[0][1]},
            "menor": {"rotulo": points[-1][0], "valor": points[-1][1]},
        }
        leader, runner_up = points[0], points[1]
        difference = leader[1] - runner_up[1]
        signals["diferenca_primeiro_segundo"] = {
            "absoluta": difference,
            "percentual_sobre_segundo": (difference / abs(runner_up[1])) if runner_up[1] else None,
        }
        ties = [label for label, value in points if value == leader[1]]
        if len(ties) > 1:
            signals["empate_na_lideranca"] = ties
        if all(value >= 0 for _, value in points):
            total = sum(value for _, value in points)
            signals["participacao_lider_no_recorte"] = leader[1] / total if total else None
        negatives = [label for label, value in points if value < 0]
        if negatives:
            signals["rotulos_com_valor_negativo"] = negatives
        if response.query_id == "Q06":
            ordered = sorted(points, key=lambda point: int(point[0]))
            first, last = ordered[0], ordered[-1]
            signals["variacao_no_periodo"] = {
                "inicio": {"rotulo": first[0], "valor": first[1]},
                "fim": {"rotulo": last[0], "valor": last[1]},
                "absoluta": last[1] - first[1],
            }
        return signals

    def _parse(self, answer: str | None) -> tuple[str, ...]:
        if not answer or answer.strip() in {"[]", "- []"}:
            return ()
        insights: list[str] = []
        for line in answer.splitlines():
            normalized = re.sub(r"^\s*(?:[-•]|\d+[.)])\s*", "", line).strip()
            if normalized and len(normalized) <= 280:
                insights.append(normalized)
            if len(insights) == self.max_insights:
                break
        return tuple(insights)
