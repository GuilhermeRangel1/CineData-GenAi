"""Orquestração do agente sem acoplar um provedor específico."""

import json
import logging
from collections.abc import Sequence
from typing import Any, Protocol

from app.agent_models import AgentResponse, ModelTurn, ToolCall, ToolDefinition
from app.errors import QueryExecutionError, QueryTimeoutError, SqlValidationError
from app.evaluation_cases import MANDATORY_EVALUATIONS, find_evaluation_case
from app.gold_database import EXPECTED_TABLES
from app.sql_executor import GoldQueryExecutor
from app.sql_guard import validate_sql


class AgentError(RuntimeError):
    """Falha controlada no ciclo de tool calling."""


class AgentClarification(AgentError):
    """A pergunta exige esclarecimento antes de consultar o Gold."""


logger = logging.getLogger(__name__)


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
_GOLD_SCHEMA_CONTEXT = "\n".join(
    (
        "dim_movies: sk_movie_id, id_filme, titulo, data_lancamento, ano_lancamento, "
        "duracao_minutos, idioma_original, status_filme, sinopse, url_poster, url_backdrop",
        "fact_movies_performance: sk_movie_id, orcamento_usd, receita_usd, lucro_usd, "
        "orcamento_brl, receita_brl, lucro_brl, popularidade, nota_tmdb, qtd_tmdb, "
        "nota_imdb, qtd_imdb",
        "dim_genres: sk_genre_id, nome_genero",
        "dim_people: sk_person_id, nome_pessoa, tipo_pessoa",
        "dim_companies: sk_company_id, nome_produtora",
        "dim_reviews: sk_review_id, sk_movie_id, qtd_avaliacoes_usuarios, nota_media_usuarios",
        "movie_reviews: id, sk_movie_review_id, sk_movie_id, name, rating, text, created_at",
        "bridge_movie_genre: sk_movie_id, sk_genre_id",
        "bridge_movie_person: sk_movie_id, sk_person_id",
        "bridge_movie_company: sk_movie_id, sk_company_id",
    )
)
_GOLD_RELATIONSHIPS_CONTEXT = (
    "Use estas chaves nos JOINs: fact_movies_performance.sk_movie_id = "
    "dim_movies.sk_movie_id; bridge_movie_genre.sk_movie_id = dim_movies.sk_movie_id; "
    "bridge_movie_genre.sk_genre_id = dim_genres.sk_genre_id; "
    "bridge_movie_person.sk_movie_id = dim_movies.sk_movie_id; "
    "bridge_movie_person.sk_person_id = dim_people.sk_person_id; "
    "bridge_movie_company.sk_movie_id = dim_movies.sk_movie_id; "
    "bridge_movie_company.sk_company_id = dim_companies.sk_company_id. "
    "Todo JOIN deve declarar sua condição; nunca use JOIN sem ON ou USING."
)


def _format_evaluation_context(case) -> str:
    """Formata um caso obrigatório com seu contrato semântico disponível."""

    context = (
        f"{case.query_id}: {case.question} Colunas esperadas: {', '.join(case.expected_columns)}."
    )
    semantic_fields = (
        ("Métrica", case.metric),
        ("Unidade", case.unit),
        ("Período", case.period),
        ("População válida", case.population),
        ("Limitações", case.limitations),
    )
    for label, value in semantic_fields:
        if value:
            context += f" {label}: {value}."
    return context


_MANDATORY_QUESTIONS_CONTEXT = "\n".join(
    _format_evaluation_context(case) for case in MANDATORY_EVALUATIONS
)

_RESPONSE_POLICY = (
    "Na resposta final, escreva em português e use somente números, nomes e "
    "conclusões sustentados pelo resultado de run_sql. Explique qual métrica foi "
    "calculada, sua unidade, o período e os filtros ou população válida. Declare "
    "limitações relevantes, como valores nulos excluídos, empate ou associação "
    "multigênero. Não invente linhas, valores, datas ou contagens que não estejam "
    "no resultado da ferramenta. Se a pergunta não definir uma métrica, unidade "
    "ou período essencial, peça esclarecimento em vez de escolher uma regra sem "
    "informar o usuário."
    " Use exatamente estes rótulos em linhas separadas: Resposta:, Métrica:, "
    "Unidade:, Período:, População válida: e Limitações:. Se faltar uma métrica "
    "essencial antes da consulta, não use run_sql e responda começando por "
    "CLARIFY: seguido do esclarecimento necessário."
)

_NATURAL_LANGUAGE_RULES = (
    " Regras de interpretação para perguntas livres: quando a pessoa disser "
    "'mais bem avaliado pelo IMDb', 'melhor avaliado no IMDb' ou equivalente, "
    "interprete isso como a maior nota_imdb, nunca como a quantidade qtd_imdb. "
    "Nesse caso, filtre nota_imdb IS NOT NULL e qtd_imdb > 0; use qtd_imdb DESC, "
    "titulo ASC e sk_movie_id ASC apenas como desempates. Só peça esclarecimento "
    "quando a pergunta mencionar explicitamente quantidade de avaliações/votos ou "
    "colocar nota e quantidade como alternativas."
)

_REQUIRED_RESPONSE_LABELS = (
    "Resposta:",
    "Métrica:",
    "Unidade:",
    "Período:",
    "População válida:",
    "Limitações:",
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
        evaluation_case = find_evaluation_case(normalized_question)

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "Responda em português. Para perguntas sobre o catálogo, "
                    "use exatamente a ferramenta run_sql. Não invente números. "
                    "Use somente estes nomes exatos de tabelas Gold: "
                    f"{_GOLD_TABLES_CONTEXT}. Não invente nomes de tabelas."
                    " Use somente as colunas reais abaixo; não traduza nomes de colunas "
                    "nem invente aliases para colunas usadas nos JOINs:\n"
                    f"{_GOLD_SCHEMA_CONTEXT}\n"
                    f"{_GOLD_RELATIONSHIPS_CONTEXT}\n"
                    f"\n{_RESPONSE_POLICY}"
                    f"\n{_NATURAL_LANGUAGE_RULES}"
                    "\nIdentifique a intenção entre os casos obrigatórios abaixo e use "
                    "aliases iguais às colunas esperadas quando fizer sentido:\n"
                    f"{_MANDATORY_QUESTIONS_CONTEXT}"
                ),
            },
            {"role": "user", "content": normalized_question},
        ]
        first_turn = self.model.complete(messages, (RUN_SQL_TOOL,))
        if first_turn.tool_call is None:
            clarification = self._extract_clarification(first_turn.answer)
            if clarification:
                raise AgentClarification(clarification)
        call = self._require_tool_call(first_turn)
        if call.name != RUN_SQL_TOOL.name:
            raise AgentError("O modelo solicitou uma ferramenta não permitida.")

        query = call.arguments.get("sql")
        if not isinstance(query, str):
            raise AgentError("A ferramenta recebeu argumentos inválidos.")

        try:
            validated = validate_sql(query, max_rows=self.max_rows)
            result = self.executor.execute(validated)
        except (SqlValidationError, QueryExecutionError, QueryTimeoutError) as exc:
            logger.warning("Consulta GenAI rejeitada: %s | SQL: %s", exc, query)
            raise AgentError("A consulta solicitada não pôde ser executada.") from exc

        if evaluation_case and result.columns != evaluation_case.expected_columns:
            raise AgentError(
                f"A consulta da {evaluation_case.query_id} não retornou as colunas "
                "obrigatórias da métrica."
            )

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
        final_answer = final_turn.answer.strip()
        if evaluation_case:
            self._validate_final_answer(final_answer)

        return AgentResponse(
            answer=final_answer,
            rows=result.rows,
            truncated=result.truncated,
            tool_calls=1,
            columns=result.columns,
            query_id=evaluation_case.query_id if evaluation_case else None,
            metric=evaluation_case.metric if evaluation_case else None,
            unit=evaluation_case.unit if evaluation_case else None,
            period=evaluation_case.period if evaluation_case else None,
            population=evaluation_case.population if evaluation_case else None,
            limitations=evaluation_case.limitations if evaluation_case else None,
        )

    @staticmethod
    def _require_tool_call(turn: ModelTurn) -> ToolCall:
        if turn.tool_call is None:
            raise AgentError("O modelo não solicitou a ferramenta de consulta.")
        return turn.tool_call

    @staticmethod
    def _extract_clarification(answer: str | None) -> str | None:
        """Obtém pedido explícito de esclarecimento emitido pelo modelo."""

        if not answer:
            return None
        normalized = answer.strip()
        if not normalized.casefold().startswith("clarify:"):
            return None
        message = normalized.split(":", 1)[1].strip()
        return message or "Informe a métrica ou o período desejado."

    @staticmethod
    def _validate_final_answer(answer: str) -> None:
        """Exige o formato semântico mínimo para perguntas obrigatórias."""

        missing = [label for label in _REQUIRED_RESPONSE_LABELS if label not in answer]
        if missing:
            raise AgentError(
                "A resposta final não informou os campos obrigatórios: " + ", ".join(missing)
            )
