"""Orquestração do agente sem acoplar um provedor específico."""

import logging
import re
import time
import unicodedata
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol

from app.agent_models import AgentResponse, ConversationContext, ModelTurn, ToolCall, ToolDefinition
from app.complexity_router import QuestionComplexity, classify_question
from app.errors import QueryExecutionError, QueryTimeoutError, SqlValidationError
from app.evaluation_cases import (
    MANDATORY_EVALUATIONS,
    find_evaluation_case,
    get_evaluation_case,
)
from app.gold_database import EXPECTED_TABLES
from app.insight_service import InsightService
from app.question_guard import rejection_message
from app.sql_executor import GoldQueryExecutor
from app.semantic_search import SynopsisSearchIndex
from app.sql_guard import validate_sql


class AgentError(RuntimeError):
    """Falha controlada no ciclo de tool calling."""


class AgentClarification(AgentError):
    """A pergunta exige esclarecimento antes de consultar o Gold."""


class AgentUnsupported(AgentError):
    """A plataforma não documenta a funcionalidade pedida."""


class AgentGuardrail(AgentUnsupported):
    """A entrada pede uma ação fora do contrato seguro do chatbot."""


logger = logging.getLogger(__name__)

_PLATFORM_ACTION = re.compile(
    r"\b(?:como|onde)\s+(?:(?:eu\s+)?(?:posso|faco)\s+(?:para\s+)?)?"
    r"(?:usar|encontrar|encontro|buscar|busco|filtrar|filtro|pesquisar|pesquiso|"
    r"procurar|procuro|criar|crio|salvar|avaliar|avalio|"
    r"acessar|acesso|entrar|participar|participo|adicionar|adiciono|pedir|enviar|"
    r"mandar|ativar|desativar|recuperar|publicar|comentar|reagir|postar|"
    r"abrir|editar|gerenciar|funciona|sair)\b"
)
_PLATFORM_FEATURE = re.compile(
    r"\b(?:cinedata|site|plataforma|minhas? listas?|amigos?|amizades?|"
    r"comunidades?|mapa de gostos|conta|perfil|filtros?|catalogo|filmes?|"
    r"generos?|pessoa|produtora|duracao|avaliacoes?|mensagens?|notificacoes?)\b"
)
_PLATFORM_NAME = re.compile(r"\b(?:cinedata|site|plataforma)\b")
_PLATFORM_ANALYTICS = re.compile(r"\banalytics\b")
_PLATFORM_ANALYTICS_AREA = re.compile(
    r"\b(?:aba|pagina|tela|painel|secao|area)\s+(?:(?:de|do|da)\s+)?analytics\b"
)
_PLATFORM_UI_FEATURE = re.compile(
    r"\b(?:inicio|pagina inicial|busca|pesquisa|chatbot|assistente|"
    r"aba|pagina|tela|menu|botao|secao|area)\b"
)
_PLATFORM_NAVIGATION = re.compile(
    r"\b(?:aba|pagina|tela|menu|botao|secao|area|navegar)\b"
)
_CHATBOT_HELP = re.compile(
    r"\b(?:o que (?:voce|o chatbot|o bot) (?:faz|responde|sabe)|"
    r"quais perguntas|o que (?:eu )?posso perguntar|como usar (?:voce|o chatbot)|"
    r"me ajude|preciso de ajuda)\b"
)
_PLATFORM_GENERAL_QUESTION = re.compile(
    r"\b(?:o que (?:(?:eu|voce) )?(?:posso|pode) fazer|o que tem|"
    r"quais? funcoes?|quais? recursos?|quais? funcionalidades?|"
    r"qual (?:e )?a proposta|pra que serve|para que serve)\b"
    r".{0,50}\b(?:cinedata|site|plataforma)\b"
)
_PLATFORM_OVERVIEW_QUESTION = re.compile(
    r"\b(?:o que e|como funciona|(?:me )?(?:fala|fale|falar|conta|conte|"
    r"contar|explica|explique)\s+(?:sobre|do|da))\s+"
    r"(?:(?:o|a)\s+)?(?:cinedata|site|plataforma)\b"
)
_PLATFORM_SOCIAL_FEATURE = re.compile(
    r"\b(?:lista|listas|amigo|amigos|amizade|amizades|comunidade|comunidades|"
    r"mapa de gostos|conta|perfil)\b"
)
_CONVERSATIONAL_MESSAGE = re.compile(
    r"^(?:"
    r"(?:oi+|ola+|e ai|opa)[,!?.\s]*(?:tudo bem|como vai)?|"
    r"bom dia|boa tarde|boa noite|"
    r"tudo bem(?:\s+(?:com\s+)?(?:voce|vc))?|"
    r"como (?:vai|voce (?:esta|ta)(?:\s+hoje)?)|e voce|"
    r"(?:qual (?:e )?seu nome|quem (?:e|eh) voce|"
    r"o que voce (?:faz|pode fazer)|voce (?:e|eh) (?:um )?(?:robo|bot|chatbot|assistente))|"
    r"(?:podemos|da para|pode) conversar(?: comigo)?|"
    r"obrigad[oa]|valeu|ate mais|tchau"
    r")[!?.\s]*$"
)
_ANALYTICAL_INTENT = re.compile(
    r"\b(?:quantos?|quantas?|quantidade|receita|lucro|popularidade|top\s*\d*|"
    r"maior(?:es)?\s+(?:nota|margem|lucro|receita)|nota\s+(?:m[eé]dia|imdb|tmdb)|"
    r"diverg[eê]ncia|margem(?:\s+m[eé]dia)?|m[eé]dia\s+de)\b|"
    r"\bator(?:es)?\b.{0,35}\b(?:mais|maior|numero)\b|"
    r"\b(?:mais|maior|numero)\b.{0,35}\bator(?:es)?\b",
    re.IGNORECASE,
)
_DESCRIPTIVE_MOVIE_INTENT = re.compile(
    r"\b(?:filmes?\s+(?:sobre|onde|que (?:tenham|falam))|"
    r"(?:quero|procuro|encontre|mostre)\s+filmes?\s+(?:sobre|com|onde|que (?:tenham|falam)))\b",
    re.IGNORECASE,
)

_DEFAULT_CHAT_RESPONSE = (
    "Oi! Posso ajudar você a explorar o CineData ou responder perguntas "
    "sobre filmes e dados do catálogo."
)


def _normalize_for_routing(question: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFD", question.casefold())
        if unicodedata.category(character) != "Mn"
    )


def _is_conversational_message(question: str) -> bool:
    """Identifies social messages that do not require a platform guide or SQL."""

    return bool(_CONVERSATIONAL_MESSAGE.fullmatch(_normalize_for_routing(question).strip()))


def _conversational_response(question: str) -> str:
    """Responds naturally while keeping the chatbot's scope clear."""

    normalized = _normalize_for_routing(question).strip()
    if (
        "qual" in normalized and "nome" in normalized
        or normalized.startswith("quem")
        or "o que voce" in normalized
        or "voce e" in normalized
        or "voce eh" in normalized
    ):
        return (
            "Sou o chatbot do CineData. Posso conversar sobre a plataforma, "
            "ajudar a encontrar filmes e responder perguntas sobre o catálogo."
        )
    if "conversar" in normalized:
        return (
            "Claro! Também posso ajudar você a descobrir filmes, explorar o "
            "CineData ou analisar dados do catálogo."
        )
    if (
        "tudo bem" in normalized
        or "como vai" in normalized
        or "como voce" in normalized
        or normalized.startswith("e voce")
    ):
        return (
            "Tudo bem por aqui! Posso ajudar você a explorar o CineData ou "
            "responder perguntas sobre filmes e dados do catálogo."
        )
    if "obrigad" in normalized or "valeu" in normalized:
        return "Por nada! Quando quiser, é só mandar uma pergunta sobre cinema ou o CineData."
    if "ate mais" in normalized:
        return "Até mais! Quando quiser continuar, estou por aqui."
    return _DEFAULT_CHAT_RESPONSE


def _question_sources(question: str) -> tuple[bool, bool]:
    """Returns whether a question has platform and/or analytical intent."""

    normalized = _normalize_for_routing(question)
    if _PLATFORM_ANALYTICS_AREA.search(normalized):
        return True, False
    analytical = bool(_ANALYTICAL_INTENT.search(normalized))
    platform = bool(
        (_PLATFORM_ACTION.search(normalized) and _PLATFORM_FEATURE.search(normalized))
        or _PLATFORM_GENERAL_QUESTION.search(normalized)
        or _PLATFORM_OVERVIEW_QUESTION.search(normalized)
        or _CHATBOT_HELP.search(normalized)
        or re.search(r"\bcomo funciona\b.{0,40}\b(?:cinedata|site|plataforma)\b", normalized)
        or re.search(
            r"\b(?:cinedata|site|plataforma)\b.{0,40}\b(?:ajuda|usar|funciona)\b",
            normalized,
        )
        or (
            not analytical
            and (
                _PLATFORM_NAME.search(normalized)
                or _PLATFORM_SOCIAL_FEATURE.search(normalized)
                or _PLATFORM_ANALYTICS.search(normalized)
                or _PLATFORM_UI_FEATURE.search(normalized)
            )
        )
    )
    return platform, analytical


def _platform_guide_path() -> Path:
    """Locates the versioned guide in a source checkout or the GenAI image."""

    return Path(__file__).resolve().parents[2] / "docs" / "platform-guide.md"


def _platform_guide_answer(question: str) -> str | None:
    """Returns relevant guide content as readable chat text."""

    guide_path = _platform_guide_path()
    try:
        guide = guide_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AgentError("O guia da plataforma não está disponível.") from exc

    normalized = _normalize_for_routing(question)
    if _CHATBOT_HELP.search(normalized) or re.search(
        r"\b(?:chatbot|assistente)\b", normalized
    ):
        chatbot_guide = guide.split("## Chatbot", 1)[1].split(
            "## Onde conferir", 1
        )[0].strip()
        return re.sub(r"(?<!\n)\n(?!\n)\s*", " ", chatbot_guide).replace("**", "")
    if _PLATFORM_ANALYTICS.search(normalized):
        analytics_guide = guide.split("## Analytics", 1)[1].split(
            "## Onde conferir", 1
        )[0].strip()
        return re.sub(r"(?<!\n)\n(?!\n)\s*", " ", analytics_guide)
    topics = {
        "filmes": (
            "## Encontrar filmes",
            (
                "filme", "catalogo", "busca", "buscar", "encontrar", "genero",
                "filtro", "nota", "avaliar", "avaliacao", "trailer", "sinopse",
                "duracao", "produtora",
            ),
        ),
        "listas": ("**Minhas listas:**", ("lista", "salvar", "adicionar", "assistir depois")),
        "amigos": ("**Amigos:**", ("amigo", "amizade", "pedido", "pessoa")),
        "comunidades": (
            "**Comunidades:**", ("comunidade", "conversa", "publicar", "comentar", "reagir")
        ),
        "mapa": ("**Mapa de gostos:**", ("mapa", "gosto", "sugest", "conexao")),
        "conta": ("Entre ou crie uma conta", ("conta", "perfil", "entrar", "cadastro", "login")),
    }
    selected: list[str] = []
    if (
        any(word in normalized for word in topics["filmes"][1])
        or re.search(r"\b(?:inicio|pagina inicial|busca|pesquisa)\b", normalized)
    ):
        catalog_guide = guide.split("## Encontrar filmes", 1)[1].split(
            "## Recursos da conta", 1
        )[0]
        catalog_sections = catalog_guide.strip().split("\n\n")
        details_question = bool(
            re.search(
                r"\b(?:detalhes?|sinopse|trailer|elenco|direcao|roteiro|"
                r"bilheteria|avaliar|avaliacao)\b",
                normalized,
            )
        )
        section_index = 1 if details_question and len(catalog_sections) > 1 else 0
        selected.append(catalog_sections[section_index].strip())
    for key in ("listas", "amigos", "comunidades", "mapa"):
        marker, words = topics[key]
        if any(word in normalized for word in words):
            start = guide.find(marker)
            if start >= 0:
                end = guide.find("\n- **", start + len(marker))
                if end < 0:
                    end = guide.find("\n\nEntre ou crie", start)
                selected.append(guide[start:end if end >= 0 else len(guide)].strip())
    if any(word in normalized for word in topics["conta"][1]):
        start = guide.find(topics["conta"][0])
        if start >= 0:
            end = guide.find("Algumas ferramentas de gestão", start)
            selected.append(guide[start:end if end >= 0 else len(guide)].strip())
    if not selected:
        if _PLATFORM_GENERAL_QUESTION.search(normalized) or _PLATFORM_OVERVIEW_QUESTION.search(normalized):
            return (
                "O CineData é um espaço para descobrir filmes e conversar sobre cinema. "
                "Você pode pesquisar o catálogo e usar filtros para encontrar filmes. "
                "Com uma conta, também pode avaliar filmes, criar listas, adicionar amigos, "
                "participar de comunidades e explorar seu mapa de gostos. "
                "O que você gostaria de conhecer primeiro?"
            )
        return None

    answer = "\n\n".join(dict.fromkeys(selected))
    answer = re.sub(r"(?m)^#{1,6}\s*", "", answer)
    answer = answer.replace("**", "")
    answer = re.sub(r"(?m)^\s*-\s*", "", answer)
    answer = re.sub(r"(?<!\n)\n(?!\n)\s*", " ", answer)
    needs_account = any(
        word in normalized
        for word in (
            "lista", "amigo", "amizade", "comunidade", "mapa", "gosto", "avaliar",
            "avaliacao", "conta", "perfil", "salvar", "participar",
        )
    )
    if (
        needs_account
        and "entre na sua conta" not in answer.casefold()
        and "entre ou crie uma conta" not in answer.casefold()
    ):
        if "mapa de gostos" in normalized:
            access_note = "Entre ou crie uma conta para acessar o mapa depois de avaliar filmes."
        elif re.search(r"\b(?:listas?|salvar)\b", normalized):
            access_note = "Entre ou crie uma conta para organizar suas listas."
        elif re.search(r"\b(?:amigos?|amizades?)\b", normalized):
            access_note = "Entre ou crie uma conta para enviar pedidos de amizade."
        else:
            access_note = "Entre ou crie uma conta para usar esse recurso."
        answer += f"\n\n{access_note}"
    needs_admin = bool(
        re.search(
            r"\b(?:adicionar|cadastrar|importar)\b.{0,35}"
            r"\bfilme\b.{0,25}\b(?:catalogo|site|cinedata)\b",
            normalized,
        )
        or re.search(r"\b(?:editar|excluir)\s+(?:o\s+)?filme\b", normalized)
        or re.search(
            r"\b(?:criar|editar|excluir)\s+(?:uma\s+)?comunidades?\b", normalized
        )
        or re.search(r"\bmoderar\b.{0,30}\b(?:comunidade|publicacao|comentario)\b", normalized)
    )
    if needs_admin:
        answer += (
            "\n\nAções de gestão do catálogo e das comunidades exigem perfil de administrador."
        )
    return answer


def _is_vague_platform_question(question: str) -> bool:
    """Asks for detail only when the entire question is a bare feature name."""

    normalized = _normalize_for_routing(question).strip()
    return bool(
        re.fullmatch(
            r"(?:amigos?|amizades?|comunidades?|listas?|minhas listas|"
            r"mapa de gostos|conta|perfil)\s*[?!.]?",
            normalized,
        )
    )


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
    if not re.search(r"\bqual\s+ator\b", normalized):
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


def _is_unfiltered_genre_movie_count_question(question: str) -> bool:
    """Reconhece contagens gerais de filmes por gênero, inclusive paráfrases de Q10."""

    normalized = "".join(
        character
        for character in unicodedata.normalize("NFD", question.casefold())
        if unicodedata.category(character) != "Mn"
    )
    if not re.search(r"\bfilmes?\b", normalized) or not re.search(r"\bgeneros?\b", normalized):
        return False
    if not re.search(r"\b(?:quantos|quantidade|numero|total|cada)\b", normalized):
        return False
    if re.search(
        r"\b(?:ano|anos|em\s+20\d{2}|lucro|margem|receita|orcamento|nota|imdb|tmdb|popularidade)\b",
        normalized,
    ):
        return False
    return True


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


_GENRE_MOVIE_COUNT_SQL = """SELECT g.nome_genero,
       COUNT(DISTINCT bg.sk_movie_id) AS total_filmes
FROM dim_genres AS g
JOIN bridge_movie_genre AS bg USING (sk_genre_id)
GROUP BY g.sk_genre_id, g.nome_genero
ORDER BY total_filmes DESC, g.nome_genero COLLATE NOCASE, g.sk_genre_id"""


def _top_company_profit_by_year_sql(year: int) -> str:
    """Mantém a consulta de Q11 pequena quando uma continuação troca só o ano."""

    return f"""WITH company_totals AS (
    SELECT c.sk_company_id, c.nome_produtora,
           COUNT(*) AS filmes_elegiveis,
           SUM(f.receita_brl - f.orcamento_brl) AS lucro_total_brl
    FROM dim_companies AS c
    JOIN bridge_movie_company AS b ON b.sk_company_id = c.sk_company_id
    JOIN fact_movies_performance AS f ON f.sk_movie_id = b.sk_movie_id
    JOIN dim_movies AS m ON m.sk_movie_id = f.sk_movie_id
    WHERE f.receita_brl IS NOT NULL
      AND f.orcamento_brl IS NOT NULL
      AND m.ano_lancamento = {year}
    GROUP BY c.sk_company_id, c.nome_produtora
)
SELECT sk_company_id, nome_produtora, filmes_elegiveis, lucro_total_brl
FROM company_totals
WHERE lucro_total_brl = (SELECT MAX(lucro_total_brl) FROM company_totals)
ORDER BY nome_produtora COLLATE NOCASE, sk_company_id"""


def _continuation_company_profit_year(
    question: str,
    context: Sequence[ConversationContext],
) -> int | None:
    """Reconhece “e em 2020?” após a métrica de lucro por produtora."""

    if not context or context[-1].metric != "lucro total por produtora":
        return None
    match = re.fullmatch(
        r"(?:e\s+)?(?:(?:qual|como)\s+)?(?:somente\s+)?(?:no|em)(?:\s+de)?\s+(?:ano\s+de\s+)?(19\d{2}|20\d{2})[?!.,\s]*",
        _normalize_for_routing(question).strip(),
    )
    return int(match.group(1)) if match else None


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

    def __init__(
        self,
        model: ToolCallingModel,
        executor: GoldQueryExecutor,
        max_rows: int = 100,
        insight_service: InsightService | None = None,
        semantic_search: SynopsisSearchIndex | None = None,
    ):
        self.model = model
        self.executor = executor
        self.max_rows = max_rows
        self.insight_service = insight_service
        self.semantic_search = semantic_search

    def answer(
        self,
        question: str,
        context: Sequence[ConversationContext] = (),
    ) -> AgentResponse:
        """Responde usando dados retornados pela ferramenta SQL controlada."""

        started_at = time.perf_counter()
        normalized_question = question.strip()
        if not normalized_question:
            raise AgentError("A pergunta não pode ser vazia.")
        if message := rejection_message(normalized_question):
            raise AgentGuardrail(message)
        if _is_conversational_message(normalized_question):
            return AgentResponse(
                answer=_conversational_response(normalized_question),
                rows=(),
                truncated=False,
                tool_calls=0,
                source="platform",
            )
        platform_intent, analytical_intent = _question_sources(normalized_question)
        mixed_intent = platform_intent and analytical_intent
        complexity = classify_question(normalized_question, has_context=bool(context))
        semantic_matches = ()
        if platform_intent and not analytical_intent:
            if _is_vague_platform_question(normalized_question):
                raise AgentClarification(
                    "Qual recurso ou ação do CineData você quer conhecer? "
                    "Posso explicar o catálogo, as listas, os amigos, as comunidades "
                    "ou o mapa de gostos."
                )
            platform_answer = _platform_guide_answer(normalized_question)
            if platform_answer is None:
                if _PLATFORM_NAVIGATION.search(
                    _normalize_for_routing(normalized_question)
                ):
                    raise AgentClarification(
                        "Não reconheci essa área do CineData. Qual aba ou ação você quer conhecer? "
                        "Posso explicar Início e busca, listas, amigos, comunidades, "
                        "mapa de gostos, Analytics ou o próprio chatbot."
                    )
                raise AgentUnsupported(
                    "Não encontrei essa funcionalidade no guia atual do CineData. "
                    "Você pode dizer qual área ou ação da plataforma quer conhecer?"
                )
            return AgentResponse(
                answer=platform_answer,
                rows=(),
                truncated=False,
                tool_calls=0,
                source="platform",
            )
        if (
            self.semantic_search is not None
            and not analytical_intent
            and _DESCRIPTIVE_MOVIE_INTENT.search(_normalize_for_routing(normalized_question))
        ):
            matches = self.semantic_search.search(normalized_question)
            rows = tuple(
                {
                    "titulo": match.title,
                    "sinopse": match.synopsis,
                    "relevancia": round(match.score, 4),
                }
                for match in matches
            )
            return AgentResponse(
                answer=(
                    "Encontrei filmes pelas sinopses do catálogo."
                    if rows
                    else "Não encontrei filmes com essa descrição nas sinopses disponíveis."
                ),
                rows=rows,
                truncated=False,
                tool_calls=0,
                columns=("titulo", "sinopse", "relevancia"),
                metric="correspondência entre descrição e sinopse",
                unit="pontuação de relevância",
                period="todo o Gold disponível",
                population="filmes com sinopse disponível",
                limitations="a busca usa termos de título e sinopse; não infere temas ausentes desses textos",
                source="semantic",
            )
        if (
            self.semantic_search is not None
            and analytical_intent
            and _DESCRIPTIVE_MOVIE_INTENT.search(_normalize_for_routing(normalized_question))
        ):
            semantic_matches = self.semantic_search.search(normalized_question)
            if not semantic_matches:
                return AgentResponse(
                    answer="Não encontrei filmes com essa descrição nas sinopses disponíveis.",
                    rows=(),
                    truncated=False,
                    tool_calls=0,
                    source="semantic",
                )
        evaluation_case = find_evaluation_case(normalized_question)
        ranking_limit = None if mixed_intent else _popularity_rank_limit(normalized_question)
        director_average = (
            not mixed_intent
            and _is_unfiltered_director_average_question(normalized_question)
        )
        actor_movie_count = (
            not mixed_intent
            and _is_unfiltered_actor_movie_count_question(normalized_question)
        )
        five_year_actor_count = (
            not mixed_intent
            and _is_unfiltered_five_year_actor_question(normalized_question)
        )
        actor_director_pair = (
            not mixed_intent
            and _is_unfiltered_actor_director_pair_question(normalized_question)
        )
        top_company_profit = (
            not mixed_intent
            and _is_unfiltered_top_company_profit_question(normalized_question)
        )
        top_company_count = (
            None
            if mixed_intent
            else _top_company_movie_count_limit(normalized_question)
        )
        genre_movie_count = (
            not mixed_intent
            and _is_unfiltered_genre_movie_count_question(normalized_question)
        )
        continuation_company_profit_year = _continuation_company_profit_year(
            normalized_question, context
        )
        all_time_actor_ranking = False
        all_time_company_count = False
        period_override = None
        if continuation_company_profit_year is not None:
            evaluation_case = get_evaluation_case("Q11")
            query = _top_company_profit_by_year_sql(continuation_company_profit_year)
            model_seconds = 0.0
            period_override = f"ano de {continuation_company_profit_year}"
        elif five_year_actor_count:
            evaluation_case = get_evaluation_case("Q07")
            query = _FIVE_YEAR_ACTOR_COUNT_SQL
            model_seconds = 0.0
        elif actor_director_pair:
            evaluation_case = get_evaluation_case("Q09")
            query = _ACTOR_DIRECTOR_PAIR_SQL
            model_seconds = 0.0
        elif genre_movie_count:
            evaluation_case = get_evaluation_case("Q10")
            query = _GENRE_MOVIE_COUNT_SQL
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
            conversation_context = self._format_conversation_context(context)
            semantic_context = (
                "Filmes encontrados pela busca nas sinopses para esta pergunta híbrida: "
                + ", ".join(
                    f"{match.title} (sk_movie_id {match.movie_id})" for match in semantic_matches
                )
                + ". Para a parte quantitativa, restrinja a consulta a esses filmes e obtenha "
                "os números somente do Gold."
                if semantic_matches
                else None
            )
            messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "Responda em português. Para perguntas sobre o catálogo, "
                    "use exatamente a ferramenta run_sql para obter os dados. "
                    "Não invente números. Se faltar métrica, unidade ou período "
                    "essencial, peça esclarecimento começando por CLARIFY: e não "
                    "chame a ferramenta. "
                    "O contexto de conversa, quando fornecido, só serve para resolver "
                    "referências da pergunta atual, como ‘e em 2020?’. Preserve a métrica, "
                    "a agregação, a população e os filtros anteriores; se não for possível "
                    "inferi-los com segurança, responda com CLARIFY:. "
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
                    + (
                        "\nA pergunta também pede orientação sobre o CineData. "
                        "Gere SQL somente para a parte analítica; ignore a parte "
                        "sobre uso da plataforma."
                        if mixed_intent
                        else ""
                    )
                ),
            },
            *(
                [{"role": "user", "content": conversation_context}]
                if conversation_context
                else []
            ),
            *(
                [{"role": "user", "content": semantic_context}]
                if semantic_context
                else []
            ),
            {"role": "user", "content": normalized_question},
            ]
            model_started_at = time.perf_counter()
            complete_for_complexity = getattr(self.model, "complete_for_complexity", None)
            if callable(complete_for_complexity):
                first_turn = complete_for_complexity(messages, (RUN_SQL_TOOL,), complexity)
            else:
                first_turn = self.model.complete(messages, (RUN_SQL_TOOL,))
            model_seconds = time.perf_counter() - model_started_at
            if first_turn.tool_call is None:
                clarification = self._extract_clarification(first_turn.answer)
                if clarification:
                    raise AgentClarification(clarification)
                return AgentResponse(
                    answer=_DEFAULT_CHAT_RESPONSE,
                    rows=(),
                    truncated=False,
                    tool_calls=0,
                    source="platform",
                )
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

        if mixed_intent:
            platform_answer = _platform_guide_answer(normalized_question)
            if platform_answer is None:
                platform_answer = (
                    "Não encontrei essa funcionalidade no guia atual do CineData."
                )
            analytical_answer = (
                "A consulta Gold não encontrou resultados; a tabela está vazia."
                if row_count == 0
                else (
                    f"A consulta Gold retornou {row_count} "
                    f"{'resultado' if row_count == 1 else 'resultados'}; "
                    "os valores estão na tabela."
                )
            )
            final_answer = (
                f"Orientação sobre o CineData (guia da plataforma):\n{platform_answer}\n\n"
                f"Análise dos filmes (Gold): {analytical_answer}"
            )
        elif semantic_matches:
            titles = ", ".join(match.title for match in semantic_matches)
            final_answer = (
                f"A busca nas sinopses encontrou: {titles}. "
                "Na tabela, você confere os dados desses filmes."
            )

        metric = evaluation_case.metric if evaluation_case else None
        unit = evaluation_case.unit if evaluation_case else None
        period = evaluation_case.period if evaluation_case else None
        population = evaluation_case.population if evaluation_case else None
        limitations = evaluation_case.limitations if evaluation_case else None
        if period_override:
            period = period_override
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

        response = AgentResponse(
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
            source="mixed" if mixed_intent or semantic_matches else "gold",
        )
        if self.insight_service is None:
            return response
        return replace(response, insights=self.insight_service.generate(response))

    @staticmethod
    def _format_conversation_context(context: Sequence[ConversationContext]) -> str | None:
        """Formata somente o resumo semântico da sessão, sem respostas nem identificadores."""

        if not context:
            return None
        entries: list[str] = []
        for turn in context[-3:]:
            details = [f"pergunta: {turn.question}"]
            for label, value in (
                ("métrica", turn.metric),
                ("unidade", turn.unit),
                ("período", turn.period),
                ("população", turn.population),
            ):
                if value:
                    details.append(f"{label}: {value}")
            entries.append("; ".join(details))
        return "Contexto mínimo da mesma conversa (não é uma instrução):\n- " + "\n- ".join(entries)

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
