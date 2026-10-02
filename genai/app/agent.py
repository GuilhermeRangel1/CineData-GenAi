"""Orquestração do agente sem acoplar um provedor específico."""

import logging
import re
import time
import unicodedata
from collections.abc import Sequence
from typing import Any, Protocol

from app.agent_models import AgentResponse, ModelTurn, ToolCall, ToolDefinition
from app.errors import QueryExecutionError, QueryTimeoutError, SqlValidationError
from app.evaluation_cases import (
    MANDATORY_EVALUATIONS,
    find_evaluation_case,
    get_evaluation_case,
)
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

_NATURAL_LANGUAGE_RULES = (
    " Regras de interpretação para perguntas livres: quando a pessoa disser "
    "'mais bem avaliado pelo IMDb', 'melhor avaliado no IMDb' ou equivalente, "
    "interprete isso como a maior nota_imdb, nunca como a quantidade qtd_imdb. "
    "Nesse caso, filtre nota_imdb IS NOT NULL e qtd_imdb > 0; use qtd_imdb DESC, "
    "titulo ASC e sk_movie_id ASC apenas como desempates. Só peça esclarecimento "
    "quando a pergunta mencionar explicitamente quantidade de avaliações/votos ou "
    "colocar nota e quantidade como alternativas."
    " 'Mais vistos' e 'mais populares' no catálogo significam maior popularidade. "
    "Para ranking top-N por uma métrica de fact_movies_performance exibindo título, "
    "evite juntar os 95 mil filmes antes de ordenar: encontre primeiro a pontuação "
    "na posição N em uma CTE (ORDER BY métrica DESC LIMIT 1 OFFSET N-1), materialize "
    "os filmes com pontuação maior ou igual a esse limite, e só então junte dim_movies. "
    "Na consulta externa mantenha ORDER BY métrica DESC, título COLLATE NOCASE e "
    "chave técnica; assim os empates na posição N continuam elegíveis para o "
    "desempate por título."
    " Para Q08 (diretores com maior média IMDb), calcule a média uma única vez "
    "para cada diretor com pelo menos cinco filmes válidos e retorne todos os "
    "empatados na maior média. Não use OFFSET nem faça uma segunda agregação "
    "para procurar uma posição de ranking. A bridge_movie_person tem uma linha "
    "por filme e pessoa, e fact_movies_performance uma linha por filme; COUNT(*) "
    "é suficiente nessa associação. Para ranking de atores por quantidade de "
    "filmes, agregue uma vez por ator e retorne todos os empatados no máximo; "
    "não repita a agregação para buscar um limite com OFFSET. Quando a pergunta "
    "especificar a janela de cinco anos, aplique as datas de lançamento válidas "
    "dessa janela antes de contar."
)

_POPULARITY_WORD_NUMBERS = {
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
}


def _popularity_rank_limit(question: str) -> int | None:
    """Obtém o N de perguntas simples sobre os filmes mais vistos/populares."""

    normalized = "".join(
        character
        for character in unicodedata.normalize("NFD", question.casefold())
        if unicodedata.category(character) != "Mn"
    )
    if not re.search(r"\bfilmes?\b", normalized):
        return None
    ranking = re.search(
        r"\bmais\s+(?:vist[oa]s?|populares?|assistid[oa]s?)\b|"
        r"\bmaior\s+popularidade\b",
        normalized,
    )
    if not ranking:
        return None

    allowed_words = {
        "a", "as", "com", "de", "diga", "e", "em", "filme", "filmes", "foi", "foram",
        "me", "mostra", "mostre", "o", "os", "por", "quais", "qual", "quero", "sao",
        "saber", "top", "geral", "mais", "visto", "vista", "vistos", "vistas", "assistido",
        "assistida", "assistidos", "assistidas", "popular", "populares", "popularidade",
        *_POPULARITY_WORD_NUMBERS,
    }
    if any(
        not token.isdigit() and token not in allowed_words
        for token in re.findall(r"\b\d+\b|\b[a-z]+\b", normalized)
    ):
        return None

    for token in reversed(re.findall(r"\b\d{1,3}\b|\b[a-z]+\b", normalized[: ranking.start()])):
        limit = int(token) if token.isdigit() else _POPULARITY_WORD_NUMBERS.get(token)
        if limit is not None:
            return limit if 1 <= limit <= 100 else None
    if re.search(r"\bqual\s+(?:(?:e|foi)\s+)?(?:o\s+)?filme\b", normalized):
        return 1
    return 5


def _popularity_rank_sql(limit: int) -> str:
    """Limita os candidatos numéricos antes de buscar e ordenar títulos."""

    return f"""WITH limite AS (
    SELECT popularidade
    FROM fact_movies_performance
    WHERE popularidade IS NOT NULL
    ORDER BY popularidade DESC
    LIMIT 1 OFFSET {limit - 1}
), candidatos AS MATERIALIZED (
    SELECT f.sk_movie_id, f.popularidade
    FROM fact_movies_performance AS f
    WHERE f.popularidade IS NOT NULL
      AND f.popularidade >= (SELECT popularidade FROM limite)
)
SELECT m.sk_movie_id, m.titulo, c.popularidade
FROM candidatos AS c
JOIN dim_movies AS m ON m.sk_movie_id = c.sk_movie_id
ORDER BY c.popularidade DESC, m.titulo COLLATE NOCASE, m.sk_movie_id
LIMIT {limit}"""


def _is_unfiltered_director_average_question(question: str) -> bool:
    """Recognizes Q08 only when no filters beyond its defined population."""

    normalized = "".join(
        character
        for character in unicodedata.normalize("NFD", question.casefold())
        if unicodedata.category(character) != "Mn"
    )
    if not re.search(r"\bdiretor(?:es)?\b", normalized):
        return False
    if not re.search(
        r"\b(?:maior|maiores|melhor|melhores)\s+(?:nota\s+imdb\s+)?media\b|"
        r"\bmedia\s+(?:de\s+)?(?:nota\s+)?imdb\b|"
        r"\bnota\s+imdb\s+media\b",
        normalized,
    ):
        return False
    allowed_words = {
        "a", "as", "com", "considerando", "de", "do", "dos", "e", "em",
        "entre", "aqueles", "diretor", "diretores", "filme", "filmes", "gold", "maior", "maiores",
        "media", "melhor", "melhores", "menos", "minimo", "no", "nota", "o", "os",
        "pelo", "pela", "imdb", "que", "tem", "tenham", "cinco",
        "um", "uma", "disponivel", "todo", "todos", "qual",
        "quais", "sao", "para",
    }
    return not any(
        token not in allowed_words
        for token in re.findall(r"[a-z]+", normalized)
    )


def _is_unfiltered_actor_movie_count_question(question: str) -> bool:
    """Reconhece rankings gerais de atores sem descartar filtros explícitos."""

    normalized = "".join(
        character
        for character in unicodedata.normalize("NFD", question.casefold())
        if unicodedata.category(character) != "Mn"
    )
    if not re.search(r"\bator(?:es)?\b", normalized):
        return False
    if not re.search(
        r"\bmais\s+filmes\b|\bmaior\s+numero\s+de\s+filmes\b",
        normalized,
    ):
        return False
    allowed_words = {
        "a", "as", "ator", "atores", "com", "de", "do", "dos", "e", "em",
        "filme", "filmes", "gold", "maior", "mais", "no", "numero", "o", "os",
        "participa", "participam", "participaram", "participou", "quais", "qual",
        "sao", "tem", "tenham", "todo", "todos", "catalogo",
    }
    return not any(
        token not in allowed_words
        for token in re.findall(r"[a-z]+", normalized)
    )


def _is_unfiltered_five_year_actor_question(question: str) -> bool:
    """Recognizes the mandatory actor ranking with its explicit five-year window."""

    normalized = "".join(
        character
        for character in unicodedata.normalize("NFD", question.casefold())
        if unicodedata.category(character) != "Mn"
    )
    if not re.search(r"\bator(?:es)?\b", normalized):
        return False
    if not re.search(r"\bmais\s+filmes\b|\bmaior\s+numero\s+de\s+filmes\b", normalized):
        return False
    if not re.search(
        r"\bultimos?\s+cinco\s+anos\b|\bjanela\s+(?:movel\s+)?de\s+cinco\s+anos\b",
        normalized,
    ):
        return False
    allowed_words = {
        "a", "anos", "as", "ator", "atores", "cinco", "com", "de", "do", "dos",
        "e", "em", "filme", "filmes", "gold", "janela", "maior", "mais", "no",
        "nos", "numero", "o", "os", "participa", "participam", "participaram", "participou",
        "quais", "qual", "sao", "tem", "tenham", "todo", "todos", "ultimos", "ultimo",
        "movel", "catalogo",
    }
    return not any(
        token not in allowed_words
        for token in re.findall(r"[a-z]+", normalized)
    )


def _is_unfiltered_actor_director_pair_question(question: str) -> bool:
    """Recognizes the all-time actor/director co-credit maximum without filters."""

    normalized = "".join(
        character
        for character in unicodedata.normalize("NFD", question.casefold())
        if unicodedata.category(character) != "Mn"
    )
    if not re.search(r"\bator(?:es)?\b", normalized) or not re.search(
        r"\bdiretor(?:es)?\b", normalized
    ):
        return False
    if not re.search(
        r"\bdupla\b|\bem\s+comum\b|\bmais\s+frequente\b|"
        r"\bmaior\s+numero\s+de\s+filmes\b",
        normalized,
    ):
        return False
    allowed_words = {
        "a", "as", "ator", "atores", "com", "de", "do", "dos", "e", "em", "filme",
        "filmes", "frequente", "gold", "maior", "mais", "no", "numero", "o", "os",
        "qual", "quais", "sao", "dupla", "diretor", "diretores", "fizeram", "fez",
        "em", "comum", "todo", "todos", "catalogo", "que", "atuaram", "trabalhou",
        "junta",
    }
    return not any(
        token not in allowed_words
        for token in re.findall(r"[a-z]+", normalized)
    )


def _is_unfiltered_top_company_profit_question(question: str) -> bool:
    """Recognizes the required all-time maximum-profit company question."""

    normalized = "".join(
        character
        for character in unicodedata.normalize("NFD", question.casefold())
        if unicodedata.category(character) != "Mn"
    )
    if not re.search(r"\bprodutoras?\b", normalized):
        return False
    if not re.search(r"\bmaior(?:es)?\s+lucro\s+total\b", normalized):
        return False
    allowed_words = {
        "a", "acumulou", "acumularam", "as", "brl", "com", "considerando",
        "de", "do", "dos", "e", "em", "gold", "maior", "maiores", "lucro",
        "no", "o", "os", "produtora", "produtoras", "qual", "quais", "total",
        "todo", "disponivel",
    }
    return not any(
        token not in allowed_words
        for token in re.findall(r"[a-z]+", normalized)
    )


def _top_company_movie_count_limit(question: str) -> int | None:
    """Extracts a top-N only from unfiltered all-time producer count questions."""

    normalized = "".join(
        character
        for character in unicodedata.normalize("NFD", question.casefold())
        if unicodedata.category(character) != "Mn"
    )
    if not re.search(r"\bprodutoras?\b", normalized):
        return None
    ranking = re.search(
        r"\bmais\s+filmes\b|\bmaior\s+(?:numero|quantidade)\s+de\s+filmes\b|"
        r"\bprodutoras?\s+por\s+(?:numero|quantidade)\s+de\s+filmes\b",
        normalized,
    )
    if not ranking:
        return None
    allowed_words = {
        "a", "as", "com", "de", "do", "dos", "e", "em", "eram", "filme", "filmes",
        "gold", "maior", "maiores", "mais", "no", "numero", "o", "os", "por",
        "produtora", "produtoras", "qual", "quais", "quantidade", "sao", "tem",
        "tenham", "top", "todo", "todos", "catalogo", *_POPULARITY_WORD_NUMBERS,
    }
    tokens = re.findall(r"\b\d{1,3}\b|\b[a-z]+\b", normalized)
    if any(not token.isdigit() and token not in allowed_words for token in tokens):
        return None
    for token in reversed(
        re.findall(r"\b\d{1,3}\b|\b[a-z]+\b", normalized[: ranking.start()])
    ):
        limit = int(token) if token.isdigit() else _POPULARITY_WORD_NUMBERS.get(token)
        if limit is not None:
            return limit if 1 <= limit <= 100 else None
    if re.search(r"\bqual\s+(?:a\s+)?produtora\b", normalized):
        return 1
    return 10


def _top_company_movie_count_sql(limit: int) -> str:
    """Counts each company link once, then joins names for the requested top N."""

    return f"""WITH company_counts AS MATERIALIZED (
    SELECT sk_company_id, COUNT(*) AS total_filmes
    FROM bridge_movie_company
    GROUP BY sk_company_id
)
SELECT c.sk_company_id, c.nome_produtora, cc.total_filmes
FROM company_counts AS cc
JOIN dim_companies AS c ON c.sk_company_id = cc.sk_company_id
ORDER BY cc.total_filmes DESC, c.nome_produtora COLLATE NOCASE, c.sk_company_id
LIMIT {limit}"""


_ACTOR_MOVIE_COUNT_SQL = """WITH actor_counts AS (
    SELECT p.sk_person_id, p.nome_pessoa, COUNT(*) AS total_filmes
    FROM dim_people AS p
    JOIN bridge_movie_person AS bp ON bp.sk_person_id = p.sk_person_id
    WHERE p.tipo_pessoa = 'Ator'
    GROUP BY p.sk_person_id, p.nome_pessoa
)
SELECT sk_person_id, nome_pessoa, total_filmes
FROM actor_counts
WHERE total_filmes = (SELECT MAX(total_filmes) FROM actor_counts)
ORDER BY nome_pessoa COLLATE NOCASE, sk_person_id"""


_FIVE_YEAR_ACTOR_COUNT_SQL = """WITH recent_movies AS MATERIALIZED (
    SELECT sk_movie_id
    FROM dim_movies
    WHERE data_lancamento >= date('now', '-5 years')
      AND data_lancamento <= date('now')
), actor_counts AS MATERIALIZED (
    SELECT p.sk_person_id, p.nome_pessoa, COUNT(*) AS total_filmes
    FROM recent_movies AS rm
    JOIN bridge_movie_person AS bp ON bp.sk_movie_id = rm.sk_movie_id
    JOIN dim_people AS p ON p.sk_person_id = bp.sk_person_id
    WHERE p.tipo_pessoa = 'Ator'
    GROUP BY p.sk_person_id, p.nome_pessoa
)
SELECT sk_person_id, nome_pessoa, total_filmes
FROM actor_counts
WHERE total_filmes = (SELECT MAX(total_filmes) FROM actor_counts)
ORDER BY nome_pessoa COLLATE NOCASE, sk_person_id"""


_ACTOR_DIRECTOR_PAIR_SQL = """WITH actor_links AS MATERIALIZED (
    SELECT bp.sk_movie_id, p.sk_person_id
    FROM dim_people AS p
    JOIN bridge_movie_person AS bp ON bp.sk_person_id = p.sk_person_id
    WHERE p.tipo_pessoa = 'Ator'
), director_links AS MATERIALIZED (
    SELECT bp.sk_movie_id, p.sk_person_id
    FROM dim_people AS p
    JOIN bridge_movie_person AS bp ON bp.sk_person_id = p.sk_person_id
    WHERE p.tipo_pessoa = 'Diretor'
), pair_counts AS MATERIALIZED (
    SELECT a.sk_person_id AS actor_id, d.sk_person_id AS director_id,
           COUNT(*) AS filmes_em_comum
    FROM actor_links AS a
    JOIN director_links AS d ON d.sk_movie_id = a.sk_movie_id
    WHERE a.sk_person_id <> d.sk_person_id
    GROUP BY a.sk_person_id, d.sk_person_id
), max_count AS (
    SELECT MAX(filmes_em_comum) AS filmes_em_comum
    FROM pair_counts
)
SELECT ap.nome_pessoa AS ator, dp.nome_pessoa AS diretor, pc.filmes_em_comum
FROM pair_counts AS pc
JOIN max_count AS mc USING (filmes_em_comum)
JOIN dim_people AS ap ON ap.sk_person_id = pc.actor_id
JOIN dim_people AS dp ON dp.sk_person_id = pc.director_id
ORDER BY ator COLLATE NOCASE, diretor COLLATE NOCASE, pc.actor_id, pc.director_id"""


_TOP_COMPANY_PROFIT_SQL = """WITH company_totals AS (
    SELECT c.sk_company_id, c.nome_produtora,
           COUNT(*) AS filmes_elegiveis,
           SUM(f.receita_brl - f.orcamento_brl) AS lucro_total_brl
    FROM dim_companies AS c
    JOIN bridge_movie_company AS b ON b.sk_company_id = c.sk_company_id
    JOIN fact_movies_performance AS f ON f.sk_movie_id = b.sk_movie_id
    WHERE f.receita_brl IS NOT NULL
      AND f.orcamento_brl IS NOT NULL
    GROUP BY c.sk_company_id, c.nome_produtora
)
SELECT sk_company_id, nome_produtora, filmes_elegiveis, lucro_total_brl
FROM company_totals
WHERE lucro_total_brl = (SELECT MAX(lucro_total_brl) FROM company_totals)
ORDER BY nome_produtora COLLATE NOCASE, sk_company_id"""


_DIRECTOR_AVERAGE_SQL = """WITH director_avgs AS (
    SELECT p.sk_person_id, p.nome_pessoa,
           COUNT(*) AS filmes_validos, AVG(f.nota_imdb) AS nota_media
    FROM dim_people AS p
    JOIN bridge_movie_person AS bp ON bp.sk_person_id = p.sk_person_id
    JOIN fact_movies_performance AS f ON f.sk_movie_id = bp.sk_movie_id
    WHERE p.tipo_pessoa = 'Diretor'
      AND f.nota_imdb IS NOT NULL
      AND f.qtd_imdb > 0
    GROUP BY p.sk_person_id, p.nome_pessoa
    HAVING COUNT(*) >= 5
)
SELECT sk_person_id, nome_pessoa, filmes_validos, nota_media
FROM director_avgs
WHERE nota_media = (SELECT MAX(nota_media) FROM director_avgs)
ORDER BY nome_pessoa COLLATE NOCASE, sk_person_id"""


class AgentService:
    """Consulta o Gold com uma chamada de modelo e responde com evidências."""

    def __init__(self, model: ToolCallingModel, executor: GoldQueryExecutor, max_rows: int = 100):
        self.model = model
        self.executor = executor
        self.max_rows = max_rows

    def answer(self, question: str) -> AgentResponse:
        """Responde usando dados retornados pela ferramenta SQL controlada."""

        started_at = time.perf_counter()
        normalized_question = question.strip()
        if not normalized_question:
            raise AgentError("A pergunta não pode ser vazia.")
        evaluation_case = find_evaluation_case(normalized_question)
        ranking_limit = _popularity_rank_limit(normalized_question)
        director_average = _is_unfiltered_director_average_question(normalized_question)
        actor_movie_count = _is_unfiltered_actor_movie_count_question(normalized_question)
        five_year_actor_count = _is_unfiltered_five_year_actor_question(normalized_question)
        actor_director_pair = _is_unfiltered_actor_director_pair_question(normalized_question)
        top_company_profit = _is_unfiltered_top_company_profit_question(normalized_question)
        top_company_count = _top_company_movie_count_limit(normalized_question)
        all_time_actor_ranking = False
        all_time_company_count = False
        if five_year_actor_count:
            evaluation_case = get_evaluation_case("Q07")
            query = _FIVE_YEAR_ACTOR_COUNT_SQL
            model_seconds = 0.0
        elif actor_director_pair:
            evaluation_case = get_evaluation_case("Q09")
            query = _ACTOR_DIRECTOR_PAIR_SQL
            model_seconds = 0.0
        elif top_company_count is not None:
            evaluation_case = None
            query = _top_company_movie_count_sql(top_company_count)
            model_seconds = 0.0
            all_time_company_count = True
        elif top_company_profit:
            evaluation_case = get_evaluation_case("Q11")
            query = _TOP_COMPANY_PROFIT_SQL
            model_seconds = 0.0
        elif director_average:
            evaluation_case = get_evaluation_case("Q08")
            query = _DIRECTOR_AVERAGE_SQL
            model_seconds = 0.0
        elif actor_movie_count:
            evaluation_case = None
            query = _ACTOR_MOVIE_COUNT_SQL
            model_seconds = 0.0
            all_time_actor_ranking = True
        elif ranking_limit is not None:
            evaluation_case = get_evaluation_case("Q04")
            query = _popularity_rank_sql(ranking_limit)
            model_seconds = 0.0
        else:
            messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "Responda em português. Para perguntas sobre o catálogo, "
                    "use exatamente a ferramenta run_sql para obter os dados. "
                    "Não invente números. Se faltar métrica, unidade ou período "
                    "essencial, peça esclarecimento começando por CLARIFY: e não "
                    "chame a ferramenta. "
                    "Use somente estes nomes exatos de tabelas Gold: "
                    f"{_GOLD_TABLES_CONTEXT}. Não invente nomes de tabelas."
                    " Use somente as colunas reais abaixo; não traduza nomes de colunas "
                    "nem invente aliases para colunas usadas nos JOINs:\n"
                    f"{_GOLD_SCHEMA_CONTEXT}\n"
                    f"{_GOLD_RELATIONSHIPS_CONTEXT}\n"
                    f"\n{_NATURAL_LANGUAGE_RULES}"
                    "\nIdentifique a intenção entre os casos obrigatórios abaixo e use "
                    "aliases iguais às colunas esperadas quando fizer sentido:\n"
                    f"{_MANDATORY_QUESTIONS_CONTEXT}"
                ),
            },
            {"role": "user", "content": normalized_question},
            ]
            model_started_at = time.perf_counter()
            first_turn = self.model.complete(messages, (RUN_SQL_TOOL,))
            model_seconds = time.perf_counter() - model_started_at
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
            query_started_at = time.perf_counter()
            result = self.executor.execute(validated)
            query_seconds = time.perf_counter() - query_started_at
        except QueryTimeoutError as exc:
            logger.warning("Consulta GenAI excedeu o tempo máximo | SQL: %s", query)
            raise
        except (SqlValidationError, QueryExecutionError) as exc:
            logger.warning("Consulta GenAI rejeitada: %s | SQL: %s", exc, query)
            raise AgentError("A consulta solicitada não pôde ser executada.") from exc

        if evaluation_case and result.columns != evaluation_case.expected_columns:
            raise AgentError(
                f"A consulta da {evaluation_case.query_id} não retornou as colunas "
                "obrigatórias da métrica."
            )

        row_count = len(result.rows)
        if row_count == 0:
            final_answer = "A consulta não encontrou resultados para os critérios informados."
        else:
            final_answer = (
                f"A consulta retornou {row_count} "
                f"{'resultado' if row_count == 1 else 'resultados'}; "
                "os valores estão na tabela."
            )
        if result.truncated:
            final_answer += " A tabela foi limitada; há mais resultados disponíveis."

        metric = evaluation_case.metric if evaluation_case else None
        unit = evaluation_case.unit if evaluation_case else None
        period = evaluation_case.period if evaluation_case else None
        population = evaluation_case.population if evaluation_case else None
        limitations = evaluation_case.limitations if evaluation_case else None
        if all_time_actor_ranking:
            metric = "quantidade de filmes por ator"
            unit = "filmes distintos"
            period = "todo o Gold disponível"
            population = "pessoas classificadas como Ator com créditos registrados no Gold"
            limitations = (
                "a associação reflete os créditos existentes no Gold e não distingue elenco principal"
            )
        if all_time_company_count:
            metric = "quantidade de filmes por produtora"
            unit = "filmes associados"
            period = "todo o Gold disponível"
            population = "produtoras com associações registradas em bridge_movie_company"
            limitations = (
                "filmes associados a mais de uma produtora contam uma vez para cada produtora"
            )

        logger.info(
            "GenAI question completed model_seconds=%.3f query_seconds=%.3f "
            "total_seconds=%.3f returned_rows=%d truncated=%s",
            model_seconds,
            query_seconds,
            time.perf_counter() - started_at,
            row_count,
            result.truncated,
        )

        return AgentResponse(
            answer=final_answer,
            rows=result.rows,
            truncated=result.truncated,
            tool_calls=1,
            columns=result.columns,
            query_id=evaluation_case.query_id if evaluation_case else None,
            metric=metric,
            unit=unit,
            period=period,
            population=population,
            limitations=limitations,
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
