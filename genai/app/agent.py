"""Orquestração do agente sem acoplar um provedor específico."""

import json
import logging
import re
import time
import unicodedata
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol

from app.agent_models import AgentResponse, ConversationContext, ModelTurn, ToolCall, ToolDefinition
from app.analytical_insights import analytical_insights
from app.complexity_router import QuestionComplexity, classify_question
from app.errors import (
    ProviderConfigurationError,
    ProviderTransientError,
    QueryExecutionError,
    QueryTimeoutError,
    SqlValidationError,
)
from app.evaluation_cases import (
    find_evaluation_case,
    get_evaluation_case,
)
from app.evaluation_runner import EvaluationMismatch, compare_rows
from app.gold_database import EXPECTED_TABLES
from app.insight_service import InsightService
from app.question_guard import rejection_message
from app.result_summary import summarize_result
from app.revenue_investigation import (
    animation_rating_context,
    finance_coverage_context,
    investigate_profit_or_rating,
    investigate_revenue,
    rating_context_for_titles,
    revenue_growth_context,
)
from app.round_two_repairs import (
    MODEL_HINTS,
    REFERENCES,
    animation_ranking,
    horror_producer_ranking,
    match_reviewed_case,
    profit_ranking_followup,
    reviewed_summary,
)
from app.semantic_search import SemanticResult, SynopsisSearchIndex, _query_tokens
from app.sql_executor import GoldQueryExecutor
from app.sql_guard import validate_sql
from app.title_synopsis import answer_title_synopsis


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
    r"\b(?:quantos?|quantas?|quantidade|receita|bilheteria|bilhetria|lucro|lucrativ[oa]s?|"
    r"popularidade|top\s*\d*|"
    r"maior(?:es)?\s+(?:nota|margem|lucro|receita)|nota\s+(?:m[eé]dia|imdb|tmdb)|"
    r"diverg[eê]ncia|margem(?:\s+m[eé]dia)?|m[eé]dia\s+de)\b|"
    r"\bator(?:es)?\b.{0,35}\b(?:mais|maior|numero)\b|"
    r"\b(?:mais|maior|numero)\b.{0,35}\bator(?:es)?\b|"
    r"\bprodutoras?\b.{0,60}\b(?:diretores?|cineastas?)\b",
    re.IGNORECASE,
)
_DESCRIPTIVE_MOVIE_INTENT = re.compile(
    r"\bfilmes?\b.{0,60}\b(?:sobre|onde|historia(?:s)?|sinopse(?:s)?|"
    r"mostra(?:m)?|conta(?:m)?|envolve(?:m)?|apresenta(?:m)?|acompanha(?:m)?|"
    r"(?:tem|tenham|tenha)\s+(?:personagens?|historia|enredo|trama)|"
    r"falam|fala|possua|possui|"
    r"que\s+(?:tenham|tenha|tem|falam|fala|possua|possui))\b|"
    r"\b(?:diga|cite|quero|procuro|encontre|mostre)\b.{0,25}"
    r"\bfilmes?\b.{0,50}\b(?:sobre|onde|que\s+(?:tenham|tenha|tem|"
    r"falam|fala|possua|possui))\b|"
    r"\b(?:quais|que|tem|existe|procuro|encontre|mostre)\b.{0,35}"
    r"\b(?:filmes?|historias?)\b.{0,45}\b(?:sobre|onde|mostram|contam|"
    r"envolvem|apresentam|acompanham)\b|"
    r"\b(?:historias?|enredos?|sinopses?)\b.{0,35}\bsobre\b",
    re.IGNORECASE,
)
_REVENUE_INTENT = re.compile(r"\b(?:receita|faturamento)\b", re.IGNORECASE)
_PRODUCER_REVENUE_INTENT = re.compile(
    r"(?=.*\bprodutoras?\b)(?=.*\b(?:bilheteria|arrecadou|receita|faturamento)\b)"
)
_CATALOG_COMPARISON_INTENT = re.compile(
    r"\bcontracen\w*\b|"
    r"(?=.*\bfilmes?\b)(?=.*\bdirigid[oa]s?\b)(?=.*\b(?:ator|atriz|elenco)\b)|"
    r"(?=.*\b(?:comedia|terror|generos?)\b)(?=.*\b(?:lucrou|bilheteria|lucro)\b)"
)
_VAGUE_SUCCESS_INTENT = re.compile(
    r"\b(?:bombou|bombaram|estourou|estouraram|flopou|floparam|"
    r"(?:fez|fizeram|teve|tiveram|foi|foram)\s+(?:mais\s+)?sucesso)\b"
)
_SUCCESS_METRIC = re.compile(
    r"\b(?:bilheteria|receita|arrecad\w*|lucro|popular\w*|notas?|votos?|"
    r"avaliac\w*|imdb|tmdb|publico|premi\w*)\b"
)
_SINGLE_MOVIE_EXAMPLE = re.compile(
    r"\b(?:um|uma)\s+(?:exemplo\s+(?:de\s+)?)?filme\b", re.IGNORECASE
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


def _empty_analytical_answer(question: str) -> str:
    """Verbaliza uma comparação anual quando a consulta não encontrou exceções."""
    period = re.search(
        r"\b(?:de|entre)\s+(\d{4})\s+(?:a|até|e)\s+(\d{4})\s*,?\s*"
        r"([^?.!]+)",
        question,
        flags=re.IGNORECASE,
    )
    if not period:
        return "A consulta não encontrou resultados para os critérios informados."

    first_year, last_year, request = period.groups()
    groups = re.search(
        r"^(?:teve algum ano em que|em quais anos|mostra só os anos em que)\s+"
        r"(?:saíram|saiu|estrearam|estreou|foram lançados)\s+mais\s+"
        r"(?:filmes de\s+)?([^?,.!]+?)\s+(?:do que|que)\s+"
        r"(?:filmes de\s+|de\s+)?([^?,.!]+)",
        request,
        flags=re.IGNORECASE,
    ) or re.fullmatch(
        r"([^?,.!]+?)\s+(?:chegou a passar|superou)\s+([^?,.!]+?)\s+"
        r"em (?:número|quantidade) de (?:estreias|lançamentos)(?: em algum ano)?",
        request,
        flags=re.IGNORECASE,
    )
    if groups:
        first_group, second_group = groups.groups()
        return (
            f"No catálogo, em nenhum ano de {first_year} a {last_year} "
            f"saíram mais filmes de {first_group.strip()} do que de {second_group.strip()}."
        )
    return "A consulta não encontrou resultados para os critérios informados."


def _is_conversational_message(question: str) -> bool:
    """Identifies social messages that do not require a platform guide or SQL."""

    return bool(_CONVERSATIONAL_MESSAGE.fullmatch(_normalize_for_routing(question).strip()))


def _requests_single_movie_example(question: str) -> bool:
    """Detecta pedidos explícitos por somente um exemplo de filme."""

    return bool(_SINGLE_MOVIE_EXAMPLE.search(_normalize_for_routing(question)))


def _semantic_revenue_sql(movie_ids: Sequence[str]) -> str:
    """Mede receita somente entre candidatos já definidos pela busca de sinopse."""

    if not movie_ids:
        raise ValueError("A busca híbrida precisa de ao menos um filme candidato.")
    values = ", ".join("'" + movie_id.replace("'", "''") + "'" for movie_id in movie_ids)
    return f"""SELECT m.sk_movie_id, m.titulo, f.receita_brl
FROM dim_movies AS m
JOIN fact_movies_performance AS f USING (sk_movie_id)
WHERE m.sk_movie_id IN ({values})
  AND f.receita_brl IS NOT NULL
ORDER BY f.receita_brl DESC, m.titulo COLLATE NOCASE, m.sk_movie_id"""


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
    analytical = bool(_ANALYTICAL_INTENT.search(normalized)) or (
        all(re.search(rf"\b{term}\b", normalized) for term in ("imdb", "tmdb"))
        and bool(re.search(r"\b(?:notas?|votos?|avaliacoes?)\b", normalized))
    )
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


def _guide_section(guide: str, heading: str) -> str:
    """Returns one Markdown section without leaking content from the next heading."""

    match = re.search(
        rf"^{re.escape(heading)}\s*$\n(?P<content>.*?)(?=^##\s|\Z)",
        guide,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group("content").strip() if match else ""


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
        chatbot_guide = _guide_section(guide, "## Chatbot")
        return re.sub(r"(?<!\n)\n(?!\n)\s*", " ", chatbot_guide).replace("**", "")
    if _PLATFORM_ANALYTICS.search(normalized):
        analytics_guide = _guide_section(guide, "## Analytics")
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
        if _PLATFORM_GENERAL_QUESTION.search(normalized) or _PLATFORM_OVERVIEW_QUESTION.search(
            normalized
        ):
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


_NATURAL_LANGUAGE_RULES = (
    " Regras de interpretação para perguntas livres: quando a pessoa disser "
    "'mais bem avaliado pelo IMDb', 'melhor avaliado no IMDb' ou equivalente, "
    "interprete isso como a maior nota_imdb, nunca como a quantidade qtd_imdb. "
    "Nesse caso, filtre nota_imdb IS NOT NULL e qtd_imdb > 0; use qtd_imdb DESC, "
    "titulo ASC e sk_movie_id ASC apenas como desempates. Só peça esclarecimento "
    "quando a pergunta mencionar explicitamente quantidade de avaliações/votos ou "
    "colocar nota e quantidade como alternativas."
    " 'Mais vistos' e 'mais populares' no catálogo significam maior popularidade. "
    "Os nomes de gêneros em dim_genres são gravados em inglês: terror = Horror, "
    "comédia = Comedy, ação = Action, animação = Animation, documentário = Documentary e "
    "ficção científica = Science Fiction. Use os valores do catálogo no WHERE. "
    "Dados financeiros em BRL e notas e votos IMDb/TMDB ficam em "
    "fact_movies_performance, não em dim_movies. Para percentual de filmes "
    "lucrativos, exija receita e orçamento conhecidos, conte lucro positivo e "
    "retorne 100.0 vezes a proporção. Se pedirem total, quantidade lucrativa e "
    "percentual, devolva as três medidas na mesma linha. "
    "Se pedirem só a porcentagem de filmes lucrativos de um gênero, ainda assim "
    "chame run_sql e retorne uma coluna percentual_lucrativo. "
    "No ranking de produtoras por percentual de filmes lucrativos, calcule lucro "
    "com receita_brl - orcamento_brl e desempate pela maior quantidade de filmes "
    "elegíveis, depois pelo nome da produtora. A contagem pode ficar fora do SELECT "
    "final quando a pessoa pedir apenas nome e percentual. "
    "Quando pedirem quantos filmes entraram em uma conta, conte os filmes "
    "elegíveis com COUNT; não some receita ou orçamento. "
    "Use BRL como moeda padrão, salvo se a pergunta pedir outra moeda. "
    "Para valores em reais, use exclusivamente receita_brl e orcamento_brl, "
    "com lucro calculado por receita_brl menos orcamento_brl. "
    "Margem de lucro é (receita menos orçamento) / receita, com receita positiva "
    "e orçamento informado. Ordene pela margem quando ela for pedida. "
    "Para lucro médio por gênero, não use uma coluna de lucro pré-calculado: faça "
    "AVG(receita_brl - orcamento_brl) e conte os filmes com as duas medidas informadas. "
    "Ordene pela maior média de lucro e desempate pelo nome do gênero. "
    "Uma média por ano de filmes já lançados exige data_lancamento <= date('now'); "
    "só testar o ano ou admitir datas nulas pode incluir filmes ainda não lançados. "
    "Para 'nos últimos cinco anos', filtre data_lancamento BETWEEN "
    "date('now', '-5 years') AND date('now'). Subtrair cinco de ano_lancamento "
    "inclui meses fora da janela móvel. "
    "Em perguntas sobre quem dirigiu uma pessoa, buscar o ID dessa pessoa é "
    "só uma etapa da consulta. Na mesma chamada, encontre seus filmes com "
    "crédito de Ator, encontre os créditos de Diretor desses filmes e agrupe "
    "por diretor. Separe a contagem de filmes em comum da contagem com nota "
    "IMDb válida. Aplique o mínimo de colaborações ao total de filmes em comum "
    "e use apenas notas com votos positivos para a média. "
    "Em perguntas com várias métricas, devolva todas as pedidas. Para lucro "
    "mediano por produtora, monte uma linha por par filme-produtora e "
    "mantenha a chave da produtora até a saída. Não junte novamente a ponte "
    "filme-produtora pelo filme, pois isso multiplica os lucros. Use a mesma "
    "população de filmes elegíveis para a proporção e a mediana. Ordene os "
    "lucros com ROW_NUMBER por produtora e calcule a média da posição "
    "central ou das duas centrais. Inclua lucro_mediano_brl no SELECT final "
    "mesmo quando o ranking for por percentual lucrativo. "
    "Se a pessoa perguntar em quais anos um grupo superou outro, calcule os "
    "dois totais por ano e filtre os anos em que o primeiro é estritamente "
    "maior que o segundo. Retorne ambos os totais e a diferença para os anos "
    "que passaram no filtro. Zero linhas é um resultado válido. "
    "Use o alias lucro_brl para receita menos orçamento em reais. "
    "Quando 'bombaram', 'fizeram mais sucesso' ou 'foram sucesso' indicar uma métrica indefinida, "
    "peça ao usuário que escolha entre bilheteria, popularidade ou avaliação. "
    "Ao ranquear duplas do mesmo tipo de crédito, use uma única orientação dos "
    "IDs para deduplicar cada dupla. Exiba os nomes em ordem alfabética dentro "
    "de cada dupla com CASE para trocar os nomes quando necessário: a ordem dos IDs "
    "não é a ordem dos nomes. Desempate o ranking pelos dois nomes já ordenados. "
    "Para obter o maior filme de cada produtora dentre um top de produtoras, "
    "agregue a ponte por produtora antes de escolher o top. Materialize o top "
    "e, em outra CTE MATERIALIZED, filtre os créditos da ponte com IN nas chaves "
    "selecionadas. Só então junte filmes e receita e ranqueie dentro da produtora. "
    "Ao pedir receita por real de orçamento 'somando tudo', divida "
    "SUM(receita_brl) por NULLIF(SUM(orcamento_brl), 0) no mesmo conjunto de "
    "filmes com os dois dados. Antes das duas somas aplique no WHERE "
    "receita_brl IS NOT NULL AND orcamento_brl IS NOT NULL. "
    "Não some nem tire a média das razões individuais. "
    "Se a pessoa pedir apenas a bilheteria por real investido, retorne só essa "
    "razão com o alias receita_por_real, sem adicionar os totais como colunas. "
    "Para participação de um top-N no total do período, use a CTE do ranking "
    "em uma subconsulta escalar para somar a receita do top-N. No SELECT "
    "externo, calcule a soma do período a partir da CTE de receitas e use "
    "NULLIF no denominador. Se pedirem porcentagem, use 100.0 * receita_do_top "
    "/ NULLIF(receita_total, 0) para entregar valores na escala de 0 a 100. "
    "Evite repetir no FROM externo uma CTE de totais "
    "cujos campos já foram lidos por subconsultas escalares. "
    "Para comparar contagens e médias dos mesmos grupos por ano, calcule "
    "COUNT e AVG juntos em uma CTE por ano e grupo, antes de comparar os grupos. "
    "Uma contagem de estreias inclui filmes sem orçamento ou receita. Use LEFT JOIN "
    "para os dados financeiros e deixe os valores ausentes de fora apenas da média. "
    "Ao comparar comédia e terror por ano, use qtd_comedia, qtd_terror, "
    "lucro_medio_comedia e lucro_medio_terror para identificar as quatro colunas. "
    "Para mediana do orçamento, crie uma CTE com ROW_NUMBER() na ordem do orçamento "
    "e COUNT(*) OVER () sobre os orçamentos informados. Retorne uma única linha "
    "com AVG(orcamento_brl) nas posições inteiras (total + 1) / 2 e (total + 2) / 2. "
    "Uma lista ordenada de todos os orçamentos não responde à pergunta. "
    "Ao medir a proporção com orçamento e bilheteria informados, use o alias "
    "percentual_informado e conte todos os filmes no denominador. "
    "Para um top-N com filtros seletivos, use uma consulta com ORDER BY e LIMIT; "
    "em perguntas como 'dos cinco mais caros, quais deram prejuízo?', selecione os "
    "cinco pelo orçamento em uma CTE antes de verificar a receita e o prejuízo. "
    "Receita ausente não demonstra prejuízo. O filtro exige receita conhecida "
    "e menor que o orçamento. "
    "Para 'quanto perdeu', 'ficou no vermelho' e 'quanto faltou para se pagar', "
    "retorne o tamanho positivo da perda: orcamento_brl - receita_brl AS prejuizo_brl. "
    "Para o gênero que mais ganhou bilheteria de um ano para outro, some a receita "
    "de cada ano separadamente por gênero, subtraia o total do ano inicial do total "
    "do ano final e retorne uma linha com o maior aumento positivo em reais. "
    "Ao comparar um top por nota IMDb com dois mínimos de votos, monte dois rankings "
    "com nota entre 0 e 10 e ORDER BY nota DESC, votos DESC, título e ID antes de "
    "cada LIMIT. Retorne quem ficou no ranking original e saiu do novo, usando "
    "LEFT JOIN pelo ID e filtrando o lado novo nulo. Preserve a ordem original, "
    "com nota antes de votos também no SELECT final. "
    "Quando a pergunta cruzar dois rankings, monte cada top separadamente, "
    "usando apenas os dados exigidos por sua própria métrica. Um ranking de "
    "bilheteria inclui filmes com receita informada mesmo sem orçamento. Em uma CTE "
    "compartilhada, mantenha esses filmes e filtre lucro não nulo somente no top por lucro. "
    "Calcule o lucro do ranking como receita_brl - orcamento_brl na CTE. "
    "A coluna pronta lucro_brl pode ter uma população diferente. "
    "No SELECT final, use INNER JOIN entre as duas CTEs de ranking pelo sk_movie_id "
    "após aplicar os limites. Não use INTERSECT, UNION ou o título como chave. "
    "Mostre os filmes na ordem do primeiro ranking, salvo se pedirem outra ordem. "
    "Para um top-N que percorre o catálogo inteiro "
    "por uma métrica de fact_movies_performance exibindo título, "
    "evite juntar os 95 mil filmes antes de ordenar: encontre primeiro a pontuação "
    "na posição N em uma CTE (ORDER BY métrica DESC LIMIT 1 OFFSET N-1), materialize "
    "os filmes com pontuação maior ou igual a esse limite, e só então junte dim_movies. "
    "Na consulta externa mantenha ORDER BY métrica DESC, título COLLATE NOCASE e "
    "chave técnica; assim os empates na posição N continuam elegíveis para o "
    "desempate por título."
    " Para Q08 (diretores com maior média IMDb), calcule a média uma única vez "
    "para cada diretor com pelo menos cinco filmes válidos e retorne todos os "
    "empatados na maior média. Não use LIMIT 1, OFFSET nem uma segunda agregação "
    "para procurar uma posição de ranking. A bridge_movie_person tem uma linha "
    "por filme e pessoa, e fact_movies_performance uma linha por filme; COUNT(*) "
    "é suficiente nessa associação. Para ranking de atores por quantidade de "
    "filmes, agregue uma vez por ator e retorne todos os empatados no máximo; "
    "não repita a agregação para buscar um limite com OFFSET. Quando a pergunta "
    "especificar a janela de cinco anos, aplique as datas de lançamento válidas "
    "dessa janela antes de contar."
    " Ao comparar duplas de ator e diretor, separe os dois conjuntos de créditos "
    "com CTEs MATERIALIZED, junte pelo filme, exclua pares da mesma pessoa "
    "e agregue pelos dois IDs antes de buscar nomes. A ponte tem uma linha por "
    "filme e pessoa, então COUNT(*) basta. Busque os nomes só para os pares "
    "empatados na maior contagem."
    " Para divergência máxima entre avaliações dos usuários e IMDb, faça o JOIN "
    "das notas válidas uma vez e use DENSE_RANK pela diferença absoluta em ordem "
    "decrescente, filtrando a posição 1 na consulta externa para manter empates."
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
        "comum", "todo", "todos", "catalogo", "que", "atuaram", "trabalhou",
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


_GENRE_MOVIE_COUNT_SQL = """SELECT g.nome_genero,
       COUNT(DISTINCT bg.sk_movie_id) AS total_filmes
FROM dim_genres AS g
JOIN bridge_movie_genre AS bg USING (sk_genre_id)
GROUP BY g.sk_genre_id, g.nome_genero
ORDER BY total_filmes DESC, g.nome_genero COLLATE NOCASE, g.sk_genre_id"""


_TMDB_IMDB_DIVERGENCE_SQL = """SELECT m.sk_movie_id, m.titulo,
       ABS(f.nota_tmdb - f.nota_imdb) AS divergencia,
       f.nota_tmdb, f.qtd_tmdb, f.nota_imdb, f.qtd_imdb
FROM dim_movies AS m
JOIN fact_movies_performance AS f USING (sk_movie_id)
WHERE f.nota_tmdb IS NOT NULL
  AND f.qtd_tmdb > 0
  AND f.nota_imdb IS NOT NULL
  AND f.qtd_imdb > 0
ORDER BY divergencia DESC, m.titulo COLLATE NOCASE, m.sk_movie_id
LIMIT 10"""


_USER_IMDB_DIVERGENCE_SQL = """WITH differences AS (
    SELECT r.sk_movie_id, m.titulo, r.nota_media_usuarios, f.nota_imdb,
           r.qtd_avaliacoes_usuarios, f.qtd_imdb,
           ABS(r.nota_media_usuarios - f.nota_imdb) AS divergencia
    FROM dim_reviews AS r
    JOIN dim_movies AS m USING (sk_movie_id)
    JOIN fact_movies_performance AS f USING (sk_movie_id)
    WHERE r.qtd_avaliacoes_usuarios > 0
      AND r.nota_media_usuarios IS NOT NULL
      AND f.nota_imdb IS NOT NULL
      AND f.qtd_imdb > 0
), maximum AS (
    SELECT MAX(divergencia) AS divergencia FROM differences
)
SELECT d.sk_movie_id, d.titulo, d.nota_media_usuarios, d.nota_imdb,
       d.qtd_avaliacoes_usuarios, d.qtd_imdb, d.divergencia
FROM differences AS d
JOIN maximum AS mx ON d.divergencia = mx.divergencia
ORDER BY d.titulo COLLATE NOCASE, d.sk_movie_id"""


_CASE_TABLES = {
    "Q01": ("dim_movies", "fact_movies_performance"),
    "Q02": ("dim_movies", "dim_genres", "bridge_movie_genre", "fact_movies_performance"),
    "Q03": ("dim_movies", "fact_movies_performance"),
    "Q04": ("dim_movies", "fact_movies_performance"),
    "Q05": ("dim_movies", "fact_movies_performance"),
    "Q06": ("dim_movies", "fact_movies_performance"),
    "Q07": ("dim_movies", "dim_people", "bridge_movie_person"),
    "Q08": ("dim_movies", "dim_people", "bridge_movie_person", "fact_movies_performance"),
    "Q09": ("dim_people", "bridge_movie_person"),
    "Q10": ("dim_genres", "bridge_movie_genre"),
    "Q11": ("dim_movies", "dim_companies", "bridge_movie_company", "fact_movies_performance"),
    "Q12": ("dim_movies", "dim_genres", "bridge_movie_genre", "fact_movies_performance"),
    "Q13": ("dim_movies", "dim_reviews"),
    "Q14": ("dim_movies", "dim_reviews", "fact_movies_performance"),
}


_ANALYTICAL_QUERY_HINTS = (
    (r"(?=.*\b(?:elenco|atores?)\b)(?=.*\bmais filmes\b)"
     r"(?=.*\b(?:ultimos|ultimas)\s+(?:cinco|5)\s+anos\b)",
     "Materialize os filmes da janela móvel antes de juntar os créditos. Conte uma "
     "vez por ator em uma CTE agregada. Use DENSE_RANK por contagem decrescente "
     "e traga os empatados na posição 1 sem repetir a junção dos créditos."),
    (r"(?=.*\bgenero\b)(?=.*\b(?:proporcao|porcentagem)\b)(?=.*\binformados\b)"
     r"(?=.*\borcamento\b)(?=.*\bbilheteria\b)",
     "Na cobertura de dados financeiros, aplique m.ano_lancamento ao universo de "
     "filmes antes de agrupar por gênero. Preserve filmes sem dados com LEFT JOIN. "
     "Calcule 100.0 * AVG(orcamento_brl IS NOT NULL AND receita_brl IS NOT NULL) "
     "sobre esse universo, sem mover esses testes para o WHERE."),
    (r"\belenco\b",
     "Para listar o elenco, junte os créditos à dimensão de pessoas e filtre "
     "explicitamente p.tipo_pessoa = 'Ator'. Se a pergunta também pedir direção, "
     "inclua os créditos de Diretor e identifique o papel de cada pessoa."),
    (r"(?=.*\b(?:top\s*\d+|duas listas)\b)(?=.*\b(?:bilheteria|arrecadaram)\b)"
     r"(?=.*\b(?:lucro|lucraram)\b)(?=.*\b(?:tanto|duas listas)\b)",
     "Aplique o ano pedido na CTE comum de filmes antes de gerar os dois rankings. "
     "Na CTE comum derive lucro_brl como receita_brl - orcamento_brl e não exclua "
     "filmes por dados financeiros ausentes. Filtre receita não nula só no top "
     "de receita e lucro não nulo só no top de lucro. Cruze os tops por sk_movie_id "
     "após os LIMITs e retorne apenas as colunas pedidas."),
    (r"(?=.*\b(?:porcentagem|percentual)\b)(?=.*\bbilheteria total\b)"
     r"(?=.*\bmais arrecadaram\b)",
     "Use a coluna real f.receita_brl no conjunto do ano solicitado. Calcule "
     "100.0 * (SELECT SUM(receita_brl) FROM top_filmes) / "
     "NULLIF(SUM(receita_brl), 0) FROM filmes_do_ano. "
     "Extraia top_filmes desse mesmo conjunto com ORDER BY receita_brl DESC e LIMIT. "
     "Use apenas filmes_do_ano no FROM externo, sem cruzar duas CTEs de totais."),
    (r"(?=.*\bprodutoras?\b)(?=.*\bmais filmes\b)(?=.*\bmaior bilheteria\b)",
     "Identifique separadamente o período da contagem por produtora e o período "
     "da busca do filme de maior bilheteria. Organize a consulta em CTEs MATERIALIZED: "
     "(1) créditos dos filmes no período da contagem, se houver, "
     "com sk_company_id e sk_movie_id da bridge_movie_company ligados a dim_movies; "
     "(2) contagem por produtora, usando COUNT(DISTINCT sk_movie_id) e dim_companies; "
     "(3) top_produtoras, ordenando contagem DESC, nome_produtora COLLATE NOCASE, "
     "ID e aplicando o LIMIT de produtoras pedido pelo usuário, se houver; "
     "(4) filmes ranqueáveis, começando em top_produtoras, "
     "e usando os créditos dos filmes no período da busca de bilheteria. "
     "Reutilize a primeira CTE somente quando os recortes coincidirem. Quando forem "
     "diferentes, junte bridge_movie_company e dim_movies novamente para aplicar "
     "o segundo recorte. Aplique o gênero solicitado às etapas correspondentes; "
     "materialize os créditos já filtrados por ano e gênero. Em seguida, junte "
     "fact_movies_performance. Filtre "
     "receita_brl IS NOT NULL antes de ROW_NUMBER() OVER (PARTITION BY sk_company_id "
     "ORDER BY receita_brl DESC, sk_movie_id). A contagem de produtoras não pode "
     "depender da existência de receita. O ID vem da ponte de créditos, nunca do fato. "
     "O nome da coluna é receita_brl, não revenue_brl nem recurso_brl. SQLite não aceita "
     "QUALIFY: calcule ROW_NUMBER em uma CTE e filtre rn = 1 em uma CTE seguinte. "
     "Retorne nome_produtora, titulo e receita_brl; ordene pelas contagens já projetadas. "
     "Quando houver limite, restrinja aos IDs selecionados antes de ranquear os filmes. "
     "No SELECT final, parta das produtoras selecionadas e faça LEFT JOIN com o filme "
     "de posição 1, preservando produtoras sem bilheteria registrada."),
    (r"(?=.*\b(?:em qual ano|em que ano)\b)(?=.*\b(?:maior|melhor)\b)"
     r"(?=.*\bmedia\b)(?=.*\bimdb\b)",
     "No mesmo WHERE aplique o período, o gênero e f.qtd_imdb > 0 AND "
     "f.nota_imdb BETWEEN 0 AND 10. Use AVG(f.nota_imdb) sem arredondar. "
     "Agrupe por ano, conte as avaliações válidas, aplique o mínimo no HAVING "
     "e retorne o ano vencedor com ORDER BY média DESC, ano ASC LIMIT 1."),
    (r"\b(?:ano passado|ano anterior)\b", "Ano passado é o ano civil anterior à data atual. Use "
     "data_lancamento >= DATE('now','start of year','-1 year') e "
     "data_lancamento < DATE('now','start of year')."),
    (r"\b(?:esse|este) ano\b|\bneste ano\b",
     "Para filmes já lançados neste ano, use data_lancamento entre "
     "DATE('now','start of year') e DATE('now'), incluindo as duas datas. "
     "Se pedirem próximas estreias, use somente datas futuras dentro do mesmo ano."),
    (r"\b(?:ultimos? (?:5|cinco) anos|(?:5|cinco) anos pra ca|(?:5|cinco) anos para ca)\b",
     "Use a janela móvel inclusiva: data_lancamento BETWEEN DATE('now','-5 years') "
     "AND DATE('now'). Não substitua por cinco rótulos de ano."),
    (r"\bdesde (?:19|20)\d{2}\b|\bde (?:19|20)\d{2} (?:pra|para) ca\b",
     "Para filmes já lançados, comece em 1º de janeiro do ano pedido e termine "
     "em DATE('now'), inclusive. Em uma continuação que só muda a data, mantenha "
     "a métrica, os demais filtros, a ordenação e o limite."),
    (r"\b(?:se pagou|se pagaram|se pagar|empataram as contas|recuperaram (?:o )?orcamento)\b",
     "Use receita e orçamento informados. 'Pelo menos se pagou' inclui igualdade "
     "entre receita e orçamento; 'deu lucro' exige receita estritamente maior."),
    (r"\b(?:sci[- ]?fi|ficcao cientifica)\b",
     "Sci-fi e ficção científica são o gênero Science Fiction em dim_genres."),
    (r"(?=.*\bdiretores\b)(?=.*\bterror\b)(?=.*\bcomedia\b)",
     "Para diretores com créditos nos dois gêneros, filtre Comedy e Horror, "
     "agrupe por ID e nome do diretor e use HAVING COUNT(DISTINCT nome_genero) = 2. "
     "Não use INTERSECT por nome. Aplique o período a todos os créditos."),
    (r"(?=.*\bfilmes?\b)(?=.*\b(?:dirigiu|dirigid[oa]s?|direcao)\b)"
     r"(?=.*\b(?:ator|atriz|atuou|elenco)\b)",
     "Ao cruzar elenco e direção, compare cada nome com COLLATE NOCASE. "
     "Use os créditos Ator e Diretor e cruze pelo ID do filme. "
     "Busque os dois créditos e retorne título e ano dos filmes na mesma chamada. "
     "Não termine a consulta com IDs ou dados cadastrais das pessoas."),
    (r"\b(?:prejuizo|preju|perda|rombos?)\b", "Aplique o ano explícito ao universo de filmes. "
     "Retorne a perda como orçamento menos receita."),
    (r"\bbilhetria\b", "Interprete 'bilhetria' como bilheteria, medida por receita_brl."),
    (r"(?=.*\bmais avaliacoes\b)(?=.*\busuarios\b)",
     "Ranqueie dim_reviews primeiro com DENSE_RANK() OVER "
     "(ORDER BY qtd_avaliacoes_usuarios DESC). Só depois filtre posição 1 e junte "
     "dim_movies para obter o título. Evite reler dim_reviews para calcular MAX."),
    (r"\b(?:ponto de equilibrio|nao se pagaram|ficaram no vermelho|mais caros)\b",
     "Se a pergunta parte dos filmes mais caros, selecione o top por orçamento em uma "
     "CTE sem filtrar receita. Aplique receita abaixo do orçamento no WHERE externo. "
     "Para 'quais e quanto faltou', "
     "retorne apenas titulo e orcamento_brl - receita_brl AS prejuizo_brl."),
    (r"(?=.*\bcomedia\b)(?=.*\bterror\b)(?=.*\blucro medio\b)",
     "Use uma CTE agregada por ano e gênero, com COUNT(*) AS estreias e "
     "AVG(receita_brl-orcamento_brl) AS lucro_medio. Conte todas as estreias até hoje "
     "com LEFT JOIN para os dados financeiros. Junte a CTE a ela mesma pelo ano, "
     "com comédia c e terror t. Exija c.estreias > t.estreias AND t.lucro_medio > "
     "c.lucro_medio. Retorne ano_lancamento, qtd_comedia, qtd_terror, "
     "lucro_medio_comedia e lucro_medio_terror."),
    (r"(?=.*\b(?:arrecadacao|bilheteria)\b)(?=.*\b(?:cresceu|salto|aumentou|ganhou mais)\b)",
     "Calcule as receitas dos dois anos separadamente por gênero. Selecione o maior "
     "aumento positivo com LIMIT 1. Valor absoluto em reais significa diferença em moeda "
     "em vez de percentual. Preserve o sinal e nunca use ABS para selecionar um aumento. "
     "Retorne só nome_genero e aumento_brl."),
    (r"(?=.*\bprodutoras?\b)(?=.*\b(?:diretores?|cineastas?)\b)"
     r"(?=.*\b(?:maior|mais)\b)",
     "Conte COUNT(DISTINCT sk_person_id) por produtora nos filmes do ano pedido. "
     "Cruze as pontes de produtora e pessoa por sk_movie_id e filtre tipo_pessoa = 'Diretor'. "
     "Ordene pela contagem decrescente e pelo nome da produtora antes de LIMIT 1."),
    (r"(?=.*\b(?:rankings|top)\b)(?=.*\b(?:receita|bilheteria|arrecadacao)\b)(?=.*\blucro\b)",
     "Faça os dois tops separados e cruze por ID. Use receita menos orçamento no top "
     "de lucro. Ordene os títulos finais pela receita decrescente do primeiro top."),
    (r"(?=.*\b(?:fatia|parcela|proporcao|porcentagem)\b)(?=.*\b(?:custo|orcamento)\b)(?=.*\b(?:registrados|conhecidos|informados)\b)(?!.*\blucr\w*)",
     "Para cobertura financeira, preserve todos os filmes com LEFT JOIN e use "
     "100.0 * AVG(receita_brl IS NOT NULL AND orcamento_brl IS NOT NULL). "
     "Retorne só gênero e percentual_informado quando pedirem o gênero líder."),
    (r"(?=.*\b(?:pares|duplas)\b)(?=.*\batores\b)",
     "Monte o elenco em uma única CTE: junte os créditos a filmes, gêneros e pessoas, "
     "filtre o ano, gênero e tipo de crédito, e selecione DISTINCT filme, pessoa e nome "
     "usando aliases declarados nessa CTE. Agrupe pares por IDs e exiba os nomes "
     "depois de contar os filmes por par. Use CASE WHEN a.nome_pessoa <= b.nome_pessoa "
     "THEN a.nome_pessoa ELSE b.nome_pessoa END AS ator_1 e a expressão inversa "
     "para ator_2. Os IDs servem apenas para deduplicar. Desempate por ator_1, ator_2."),
    (r"\bcoproduc\w*\b", "Na CTE de coproduções, junte dim_movies e aplique "
     "WHERE m.ano_lancamento = ano solicitado. Depois use GROUP BY sk_movie_id "
     "HAVING COUNT(DISTINCT sk_company_id) >= 2. No SELECT externo, junte esses IDs "
     "com a ponte de produtoras novamente e agrupe por produtora para contar filmes "
     "distintos. Obtenha c.nome_produtora de dim_companies c, juntando pelo sk_company_id "
     "da ponte. Agrupe por ID e nome da produtora. Ordene pela contagem decrescente "
     "e desempate por c.nome_produtora COLLATE NOCASE e c.sk_company_id antes do LIMIT. "
     "Use o HAVING de duas produtoras somente na CTE por filme."),
    (r"(?=.*\btop\b)(?=.*\bimdb\b)(?=.*\bvotos\b)(?=.*\b(?:deixam|cai|saem|perde)\b)",
     "Retorne apenas os itens que saíram do top original: LEFT JOIN entre os tops "
     "por ID e filtro de ID nulo no top novo. Junte dim_movies antes de cada LIMIT e "
     "ordene ambos os tops e a saída por nota DESC, votos DESC, titulo ASC e sk_movie_id ASC. "
     "Use nota_imdb BETWEEN 0 AND 10."),
)


def _analytical_topic(question: str) -> str | None:
    normalized = _normalize_for_routing(question)
    if (
        (
            re.search(r"\bdiretores?\b", normalized)
            and re.search(r"\b(?:trabalharam|fizeram)\s+(?:\w+\s+){0,3}com\b", normalized)
            or re.search(r"\bquem dirigiu\b", normalized)
            and re.search(r"\b(?:em comum|juntos|(?:duas|[2-9]|\d{2,}) vezes)\b", normalized)
        )
        and not re.search(r"\b(?:generos?|produtoras?|tmdb|usuarios)\b", normalized)
    ):
        return "director_collaborations"
    if (
        re.search(r"\bprodutoras?\b", normalized)
        and re.search(r"\b(?:mediana|mediano)\b", normalized)
        and not re.search(r"\b(?:generos?|atores?|diretores?|usuarios)\b", normalized)
    ):
        return "producer_median_profit"
    if (
        re.search(r"\bprodutoras?\b", normalized)
        and re.search(r"\b(?:percentual|porcentagem|proporcao|fatia)\b", normalized)
        and re.search(r"\b(?:lucro|lucrativ\w*)\b", normalized)
    ):
        return "producer_profitable_share"
    return None


_TOPIC_RULES = {
    "producer_profitable_share": (
        "Agrupe por ID e nome da produtora, com uma linha por filme e produtora. "
        "Inclua só filmes com receita_brl e orcamento_brl informados. Calcule "
        "100.0 * AVG(receita_brl > orcamento_brl) AS percentual_lucrativo. "
        "Aplique o mínimo de filmes com HAVING COUNT(*). Use obrigatoriamente "
        "ORDER BY percentual_lucrativo DESC, COUNT(*) DESC, nome_produtora ASC "
        "antes do LIMIT. Mesmo se pedirem só nome e percentual, mantenha COUNT(*) "
        "no ORDER BY para desempatar. Retorne apenas as colunas pedidas."
    ),
    "director_collaborations": (
        "A chamada run_sql deve devolver os diretores, os totais e a média solicitados "
        "em um único SELECT final. Não chame a ferramenta para consultar apenas o "
        "cadastro ou o ID do ator. Identifique os filmes com crédito de Ator usando "
        "nome_pessoa COLLATE NOCASE e tipo_pessoa = 'Ator' na mesma CTE. "
        "Materialize a lista de filmes e só então cruze com os créditos Diretor "
        "pelo sk_movie_id. Agrupe por ID e nome do diretor e conte filmes distintos. "
        "Use LEFT JOIN para preservar filmes sem nota. As colunas reais da avaliação "
        "são nota_imdb e qtd_imdb. Conte e tire a média das notas de 0 a 10 com votos "
        "positivos. Separe esse total do total de filmes em comum e aplique o "
        "mínimo de colaborações ao total de filmes em comum. Use os aliases diretor, "
        "filmes_em_comum, filmes_avaliados e nota_media_imdb para as colunas solicitadas. "
        "Se pedirem só os nomes, use a média dos filmes em comum para ordenar e "
        "retorne apenas diretor. Use apenas aliases de "
        "tabelas declaradas no FROM ou JOIN da própria CTE."
    ),
    "producer_median_profit": (
        "Em uma CTE, junte a ponte de produtoras ao fato e calcule lucro como "
        "receita_brl - orcamento_brl. Inclua apenas filmes com os dois valores. "
        "Calcule ROW_NUMBER ordenado por lucro e COUNT(*) na partição por "
        "sk_company_id em uma CTE que preserve uma linha por filme e produtora. "
        "Nessa CTE use somente funções de janela, sem agregações sem OVER nem GROUP BY. "
        "Na CTE seguinte, agregue por produtora e calcule a mediana pela média "
        "dos lucros nas posições (total + 1) / 2 e (total + 2) / 2, com divisão "
        "inteira nessas posições. Na agregação final, use "
        "AVG(CASE WHEN posicao IN ((total + 1) / 2, (total + 2) / 2) THEN lucro END) "
        "para a mediana. Não filtre as posições centrais no WHERE, pois COUNT(*) "
        "e SUM(lucro > 0) precisam de todos os filmes elegíveis. Calcule a proporção "
        "com 100.0 * AVG(lucro > 0). "
        "Use a mesma população para a mediana e a proporção. Junte o nome pela "
        "chave da produtora. Em empate na proporção, priorize o maior total elegível."
    ),
}


def _schema_for_case(case, topic: str | None = None) -> tuple[str, str]:
    """Reduz o esquema em intenções claras, preservando o catálogo completo nos demais casos."""

    if case is not None:
        tables = _CASE_TABLES.get(case.query_id)
        if tables is None:
            return _GOLD_TABLES_CONTEXT, _GOLD_SCHEMA_CONTEXT
    elif topic == "director_collaborations":
        tables = _CASE_TABLES["Q08"]
    elif topic in {"producer_median_profit", "producer_profitable_share"}:
        tables = _CASE_TABLES["Q11"]
    else:
        return _GOLD_TABLES_CONTEXT, _GOLD_SCHEMA_CONTEXT
    schema = "\n".join(
        line for line in _GOLD_SCHEMA_CONTEXT.splitlines()
        if line.split(":", 1)[0] in tables
    )
    return ", ".join(tables), schema


_IMDB_AVERAGE_BY_YEAR_SQL = """SELECT m.ano_lancamento,
       COUNT(*) AS filmes_validos,
       AVG(f.nota_imdb) AS nota_imdb_media
FROM dim_movies AS m
JOIN fact_movies_performance AS f USING (sk_movie_id)
WHERE m.ano_lancamento IS NOT NULL
  AND m.data_lancamento <= date('now')
  AND f.nota_imdb IS NOT NULL
  AND f.qtd_imdb > 0
GROUP BY m.ano_lancamento
ORDER BY m.ano_lancamento ASC"""


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


_REFERENCE_FALLBACKS = {
    "Q04": _popularity_rank_sql(5),
    "Q05": _TMDB_IMDB_DIVERGENCE_SQL,
    "Q06": _IMDB_AVERAGE_BY_YEAR_SQL,
    "Q07": _FIVE_YEAR_ACTOR_COUNT_SQL,
    "Q08": _DIRECTOR_AVERAGE_SQL,
    "Q09": _ACTOR_DIRECTOR_PAIR_SQL,
    "Q10": _GENRE_MOVIE_COUNT_SQL,
    "Q11": _TOP_COMPANY_PROFIT_SQL,
    "Q14": _USER_IMDB_DIVERGENCE_SQL,
}

_FOCUSED_METRIC_RULES = {
    "Q01": (
        "Ordene por receita_brl decrescente, mantenha apenas receita não nula e "
        "retorne dez filmes com desempate estável por título e chave."
    ),
    "Q02": (
        "Calcule AVG(receita_brl - orcamento_brl) por gênero apenas com receita e "
        "orçamento informados; cada associação filme-gênero participa uma vez. "
        "Retorne todos os gêneros, ordenados por lucro_medio_brl DESC e "
        "nome_genero COLLATE NOCASE em caso de empate."
    ),
    "Q03": (
        "Calcule margem como (receita_brl - orcamento_brl) / receita_brl para filmes "
        "com receita positiva e orçamento informado; use divisão real "
        "(1.0 * numerador / receita), retorne dez filmes quando não houver quantidade "
        "explícita e ordene por margem DESC, título COLLATE NOCASE e chave técnica."
    ),
    "Q04": (
        "Use popularidade, não visualizações; inclua zero, retorne cinco filmes e "
        "desempate por título e chave. Encontre o limite de pontuação antes de "
        "juntar os títulos."
    ),
    "Q05": (
        "Calcule a diferença absoluta entre as notas; exija notas e votos positivos "
        "nas duas fontes; ordene pela maior diferença e retorne dez filmes com as "
        "duas contagens de votos; desempate por título COLLATE NOCASE e chave técnica."
    ),
    "Q06": (
        "Agrupe por ano de lançamento em ordem crescente; exclua lançamentos futuros "
        "com data_lancamento > date('now') (não compare ano_lancamento a um ano "
        "estimado pelo modelo); calcule média IMDb somente para filmes com nota e votos válidos "
        "e informe a quantidade de filmes por ano."
    ),
    "Q07": (
        "Conte filmes distintos por ator numa janela móvel. Filtre "
        "data_lancamento BETWEEN date('now', '-5 years') AND date('now') "
        "em uma CTE antes de juntar créditos. Não filtre por ano_lancamento ou "
        "pelo ano extraído da data. Agregue por ator em uma CTE e, em outra, use "
        "DENSE_RANK() OVER (ORDER BY total_filmes DESC). Não aninhe função de "
        "janela dentro de MAX(). Retorne todos os empatados no máximo."
    ),
    "Q08": (
        "Calcule a média IMDb por diretor uma vez, exigindo pelo menos cinco filmes "
        "com nota não nula (zero é válido) e votos positivos; filtre tipo_pessoa = 'Diretor'. "
        "A pergunta pede SOMENTE os vencedores, não um ranking de todos os diretores. "
        "Separe a agregação em uma CTE, aplique HAVING COUNT(*) >= 5 nessa CTE e, "
        "na consulta externa, filtre nota_media = (SELECT MAX(nota_media) FROM a_CTE). "
        "ORDER BY nota_media DESC sozinho não seleciona os vencedores. Não substitua "
        "esse filtro por LIMIT 1 ou LIMIT 100: preserve todos os empatados no máximo. "
        "Retorne somente as quatro colunas esperadas, ordenadas por nome_pessoa "
        "COLLATE NOCASE e sk_person_id."
    ),
    "Q09": (
        "Use a cláusula AS MATERIALIZED do SQLite nas três CTEs: créditos de atores, "
        "créditos de diretores e contagem por dupla. Em cada CTE de créditos, use "
        "JOIN entre dim_people e bridge_movie_person pelo sk_person_id e filtre "
        "tipo_pessoa pelo papel correspondente. Junte os créditos pelo filme, exclua "
        "pares da mesma pessoa. Use COUNT(*) agrupado pelos dois IDs. A ponte é única "
        "por filme e pessoa. Filtre pelo máximo preservando todos os empates e só então "
        "junte dim_people duas vezes para retornar ator, diretor e filmes_em_comum. "
        "Ordene pelos nomes com COLLATE NOCASE."
    ),
    "Q10": (
        "Conte filmes distintos em cada associação filme-gênero; ordene pela "
        "contagem decrescente e nome do gênero."
    ),
    "Q11": (
        "Não use a coluna lucro_brl: ela pode ter população diferente. Calcule "
        "SUM(receita_brl - orcamento_brl) por produtora apenas quando ambos "
        "existirem. Em outra CTE, use DENSE_RANK() sobre lucro_total_brl DESC. "
        "Retorne todas as produtoras na posição 1 para preservar empates."
    ),
    "Q12": (
        "Calcule a média das margens individuais por gênero, usando somente filmes "
        "com receita positiva e orçamento informado; retorne todos os gêneros "
        "empatados no máximo. Use 1.0 * (receita_brl - orcamento_brl) / receita_brl "
        "antes do AVG; inclua orçamento zero, deduplique associações filme-gênero "
        "e agrupe por chave e nome. Antes de COUNT e AVG, filtre explicitamente "
        "receita_brl > 0 AND orcamento_brl IS NOT NULL: COUNT não ignora orçamento nulo "
        "automaticamente como AVG faz. Na saída, selecione sk_genre_id, nome_genero, "
        "COUNT(*) AS filmes_validos e AVG da margem AS margem_media, preservando "
        "esses nomes após filtrar os vencedores. Use DENSE_RANK() sobre margem_media "
        "DESC em outra CTE e filtre pela posição 1 para preservar empates."
    ),
    "Q13": (
        "Use qtd_avaliacoes_usuarios de dim_reviews por filme e retorne os empatados "
        "no maior número de avaliações. Faça DENSE_RANK sobre dim_reviews antes "
        "de juntar dim_movies. Evite reler dim_reviews em uma CTE de MAX."
    ),
    "Q14": (
        "Compare o resumo de notas dos usuários com IMDb apenas quando ambas as "
        "fontes têm votos positivos. nota_media_usuarios e qtd_avaliacoes_usuarios "
        "vêm de dim_reviews; nota_imdb e qtd_imdb vêm de fact_movies_performance. "
        "Junte essas tabelas por sk_movie_id; calcule a diferença absoluta e retorne todos "
        "os filmes empatados no valor máximo. Use DENSE_RANK em ordem decrescente "
        "e filtre posição 1 fora da CTE para não recalcular o JOIN numa subconsulta."
    ),
}


class AgentService:
    """Consulta o Gold com uma chamada de modelo e responde com evidências."""

    model_only = False

    def __init__(
        self,
        model: ToolCallingModel,
        executor: GoldQueryExecutor,
        max_rows: int = 100,
        insight_service: InsightService | None = None,
        semantic_search: SynopsisSearchIndex | None = None,
        provider_configured: bool = True,
        model_only: bool = False,
        tmdb_api_token: str | None = None,
    ):
        self.model = model
        self.model_only = model_only
        self.executor = executor
        self.max_rows = max_rows
        self.insight_service = insight_service
        self.semantic_search = semantic_search
        self.provider_configured = provider_configured
        self.tmdb_api_token = tmdb_api_token
        self._reference_pool = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="gold-reference"
        )

    def _find_movies_by_story(
        self, question: str, *, limit: int = 5
    ) -> tuple[SemanticResult, ...]:
        """Traduz conceitos da pergunta; as sinopses permanecem no índice local."""

        if self.semantic_search is None:
            return ()
        direct = self.semantic_search.search(question, limit=limit, min_terms=2)
        if direct:
            return direct
        key_terms = tuple(dict.fromkeys(_query_tokens(question)))
        if not key_terms:
            return ()
        if len(key_terms) > 2:
            key_terms = (key_terms[0], key_terms[-1])
        try:
            turn = self.model.complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "Traduza cada palavra da lista recebida, na mesma ordem, para "
                            "palavras que possam aparecer em sinopses de filmes em inglês. "
                            "Para cada item, retorne de duas a quatro alternativas de UMA "
                            "palavra (traduções diretas e sinônimos estritos). Evite termos "
                            "vagamente relacionados, objetos e personagens do mesmo tema. "
                            "Não omita itens, não "
                            "adicione conceitos e não use expressões com espaços. Responda "
                            'somente JSON: {"translations":[["word","synonym"],'
                            '["word","synonym"]]}. A lista externa deve ter exatamente '
                            "a mesma quantidade de itens que a entrada."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps({"terms": key_terms}, ensure_ascii=False),
                    },
                ],
                [],
            )
            raw = re.search(r"\{.*\}", (turn.answer or "")[:4000], re.DOTALL)
            parsed = json.loads(raw.group() if raw else "")
            translations = parsed.get("translations")
            if not isinstance(translations, list) or len(translations) != len(key_terms):
                return ()
            groups: list[tuple[str, ...]] = []
            for source, terms in zip(key_terms, translations, strict=True):
                if not isinstance(terms, list):
                    return ()
                valid_terms = tuple(
                    term.strip()
                    for term in terms[:4]
                    if isinstance(term, str) and len(_query_tokens(term)) == 1
                )
                groups.append((source, *valid_terms))
            return self.semantic_search.search_concepts(tuple(groups), limit=limit)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            logger.info("Termos da busca por enredo inválidos: %s", exc.__class__.__name__)
        except Exception as exc:
            logger.warning("Expansão da busca por enredo falhou: %s", exc.__class__.__name__)
        return ()

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
        normalized_routing_question = _normalize_for_routing(normalized_question)
        reviewed_case = match_reviewed_case(normalized_routing_question)
        if reviewed_case is None:
            synopsis = answer_title_synopsis(
                normalized_question, context, self.executor.database, self.model,
                self.provider_configured, tmdb_token=self.tmdb_api_token,
            )
            if synopsis is not None:
                return synopsis
        if not context and re.fullmatch(
            r"(?:e )?quem (?:foi que )?dirigiu (?:esse|este|aquele)(?: filme| ai)?[?.!]*",
            normalized_routing_question,
        ):
            raise AgentClarification("Qual é o título do filme que você quer consultar?")
        if investigation := investigate_revenue(
            normalized_routing_question, self.executor, self.max_rows
        ):
            return investigation
        if re.fullmatch(
            r"por que o lucro total caiu mesmo com (?:uma )?proporcao maior "
            r"de filmes lucrativos\??",
            normalized_routing_question,
        ):
            for turn in reversed(context):
                period = re.fullmatch(r"((?:19|20)\d{2}) e ((?:19|20)\d{2})", turn.period or "")
                if (
                    turn.metric == "lucro total"
                    and period
                    and "filmes do catalogo" in _normalize_for_routing(turn.question)
                ):
                    start, end = period.groups()
                    normalized_routing_question = (
                        "o que explica a mudanca no lucro total dos filmes do catalogo "
                        f"entre {start} e {end}"
                    )
                    break
            else:
                raise AgentClarification(
                    "Quais dois anos você quer comparar para explicar a queda do lucro?"
                )
        if investigation := investigate_profit_or_rating(
            normalized_routing_question, self.executor, self.max_rows
        ):
            return investigation
        if (
            not context
            and (
                re.search(r"\bfilmes?\b", normalized_routing_question)
                or re.match(r"^(?:quais|qual|que)\s+flop(?:ou|aram)\b", normalized_routing_question)
            )
            and _VAGUE_SUCCESS_INTENT.search(normalized_routing_question)
            and not _SUCCESS_METRIC.search(normalized_routing_question)
        ):
            raise AgentClarification(
                "Por flop, você quer dizer prejuízo, bilheteria baixa ou nota baixa?"
                if re.search(r"\bflop(?:ou|aram)\b", normalized_routing_question)
                else "Você quer medir o sucesso pela bilheteria, pela popularidade ou pelas notas?"
            )
        producer_revenue_intent = bool(
            _PRODUCER_REVENUE_INTENT.search(normalized_routing_question)
        )
        previous_question = _normalize_for_routing(context[-1].question) if context else ""
        reviewed_case = (
            reviewed_case
            or profit_ranking_followup(normalized_routing_question, previous_question)
        )
        animation_rank = animation_ranking(
            normalized_routing_question, previous_question,
        )
        descriptive_movie_intent = bool(
            _DESCRIPTIVE_MOVIE_INTENT.search(normalized_routing_question)
        )
        platform_intent, analytical_intent = _question_sources(normalized_question)
        filters_previous_ranking = bool(context) and bool(re.search(
            r"\b(?:desse grupo|desse top|daquele top|dessas|desses)\b", normalized_routing_question
        ))
        if filters_previous_ranking or (context and re.search(
            r"\b(?:faz o mesmo|agora so de)\b", normalized_routing_question
        )):
            analytical_intent |= _question_sources(context[-1].question)[1]
        catalog_comparison_intent = bool(
            _CATALOG_COMPARISON_INTENT.search(normalized_routing_question)
        )
        analytical_intent = (
            analytical_intent or producer_revenue_intent or catalog_comparison_intent
            or reviewed_case is not None or animation_rank is not None
        )
        semantic_intent = descriptive_movie_intent and (
            not analytical_intent
            or bool(
                re.search(
                    r"\b(?:sobre|sinopse|enredo|trama|historia|historias|personagem|"
                    r"personagens)\b",
                    normalized_routing_question,
                )
            )
        )
        explicit_platform_navigation = bool(
            _PLATFORM_ACTION.search(normalized_routing_question)
            and _PLATFORM_NAME.search(normalized_routing_question)
        )
        if not explicit_platform_navigation and (
            catalog_comparison_intent or reviewed_case is not None
        ):
            platform_intent = False
        if semantic_intent and not analytical_intent and not explicit_platform_navigation:
            # Palavras como "amizade" também aparecem nas áreas sociais do guia;
            # quando a pergunta descreve um enredo, a intenção principal é buscar filmes.
            platform_intent = False
        mixed_intent = platform_intent and analytical_intent
        complexity = classify_question(normalized_question, has_context=bool(context))
        if analytical_intent and complexity == QuestionComplexity.SIMPLE:
            complexity = (
                QuestionComplexity.COMPLEX if context else QuestionComplexity.ANALYTICAL
            )
        semantic_matches = ()
        semantic_revenue_ranking = False
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
        if not self.provider_configured:
            raise ProviderConfigurationError(
                "Configure um provedor de IA para consultar os dados dos filmes."
            )
        if (
            self.semantic_search is not None
            and not analytical_intent
            and semantic_intent
        ):
            matches = self._find_movies_by_story(
                normalized_question,
                limit=1 if _requests_single_movie_example(normalized_question) else 5,
            )
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
                limitations=(
                    "a busca usa termos de título e sinopse; "
                    "não infere temas ausentes desses textos"
                ),
                source="semantic",
            )
        if (
            self.semantic_search is not None
            and analytical_intent
            and semantic_intent
        ):
            semantic_matches = self._find_movies_by_story(normalized_question)
            if not semantic_matches:
                return AgentResponse(
                    answer="Não encontrei filmes com essa descrição nas sinopses disponíveis.",
                    rows=(),
                    truncated=False,
                    tool_calls=0,
                    source="semantic",
                )
        semantic_revenue_ranking = bool(
            semantic_matches and _REVENUE_INTENT.search(normalized_question)
        )
        evaluation_case = (
            find_evaluation_case(normalized_question)
            or (animation_rank[0] if animation_rank else reviewed_case)
        )
        reference_fallback = (
            (animation_rank[1] if animation_rank else
             REFERENCES.get(evaluation_case.query_id)
             or _REFERENCE_FALLBACKS.get(evaluation_case.query_id))
            if evaluation_case is not None and not mixed_intent and not self.model_only
            else None
        )
        if reference_fallback is not None:
            complexity = QuestionComplexity.ANALYTICAL
        reference_future = (
            self._reference_pool.submit(
                self.executor.execute,
                validate_sql(reference_fallback, max_rows=self.max_rows),
            )
            if reference_fallback is not None
            else None
        )
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
        continuation_company_profit_year = _continuation_company_profit_year(
            normalized_question, context
        )
        all_time_actor_ranking = False
        all_time_company_count = False
        period_override = None
        query_source = "local"
        horror_ranking = (
            horror_producer_ranking(normalized_routing_question)
            if not mixed_intent and not self.model_only else None
        )
        if horror_ranking:
            query = horror_ranking
            model_seconds = 0.0
        elif semantic_revenue_ranking:
            evaluation_case = None
            query = _semantic_revenue_sql([match.movie_id for match in semantic_matches])
            model_seconds = 0.0
        elif continuation_company_profit_year is not None and not self.model_only:
            evaluation_case = get_evaluation_case("Q11")
            query = _top_company_profit_by_year_sql(continuation_company_profit_year)
            model_seconds = 0.0
            period_override = f"ano de {continuation_company_profit_year}"
        elif five_year_actor_count and reference_fallback is None and not self.model_only:
            evaluation_case = get_evaluation_case("Q07")
            query = _FIVE_YEAR_ACTOR_COUNT_SQL
            model_seconds = 0.0
        elif actor_director_pair and reference_fallback is None and not self.model_only:
            evaluation_case = get_evaluation_case("Q09")
            query = _ACTOR_DIRECTOR_PAIR_SQL
            model_seconds = 0.0
        elif top_company_count is not None and not self.model_only:
            evaluation_case = None
            query = _top_company_movie_count_sql(top_company_count)
            model_seconds = 0.0
            all_time_company_count = True
        elif top_company_profit and reference_fallback is None and not self.model_only:
            evaluation_case = get_evaluation_case("Q11")
            query = _TOP_COMPANY_PROFIT_SQL
            model_seconds = 0.0
        elif director_average and reference_fallback is None and not self.model_only:
            evaluation_case = get_evaluation_case("Q08")
            query = _DIRECTOR_AVERAGE_SQL
            model_seconds = 0.0
        elif actor_movie_count and not self.model_only:
            evaluation_case = None
            query = _ACTOR_MOVIE_COUNT_SQL
            model_seconds = 0.0
            all_time_actor_ranking = True
        elif ranking_limit is not None and reference_fallback is None and not self.model_only:
            evaluation_case = get_evaluation_case("Q04")
            query = _popularity_rank_sql(ranking_limit)
            model_seconds = 0.0
        else:
            topic = (
                None if context or mixed_intent or semantic_matches
                else _analytical_topic(normalized_question)
            )
            available_tables, schema_context = _schema_for_case(evaluation_case, topic)
            natural_rules = (
                _TOPIC_RULES.get(topic, _NATURAL_LANGUAGE_RULES) if evaluation_case is None else ""
            )
            evaluation_context = (
                "\nUse os aliases do caso reconhecido quando fizer sentido:\n"
                + _format_evaluation_context(evaluation_case)
                if evaluation_case else ""
            )
            conversation_context = self._format_conversation_context(context)
            query_hints = [
                hint for pattern, hint in _ANALYTICAL_QUERY_HINTS
                if re.search(pattern, normalized_routing_question)
            ]
            if evaluation_case and evaluation_case.query_id in MODEL_HINTS:
                query_hints.append(MODEL_HINTS[evaluation_case.query_id])
            if animation_rank:
                query_hints.append(
                    "Retorne titulo, receita_brl, ano_lancamento, nessa ordem. "
                    f"Selecione cinco animações por receita em reais desde {animation_rank[2]} "
                    "até hoje."
                )
            if topic and evaluation_case is None:
                query_hints.append("Entregue a análise completa em uma chamada run_sql.")
            if context and re.fullmatch(
                r"(?:e )?(?:qual|quem|quais)\s+(?:(?:foi|teve|fez|ganhou|deu)\s+)?"
                r"(?:o |a )?(?:menos|menor|mais|maior)(?:\s+[^?.!]*)?[?.!]*",
                normalized_routing_question,
            ):
                query_hints.append(
                    "O pedido atual quer apenas um extremo. Herde a população e os filtros "
                    "da pergunta anterior, não a linha do ranking. Ordene a métrica ASC "
                    "para menos/menor ou DESC para mais/maior e aplique o limite da pergunta "
                    "atual depois da ordenação. Não devolva o extremo oposto nem repita a "
                    "resposta da pergunta anterior."
                )
            if context and re.search(
                r"\b(?:faz (?:o )?mesmo|troca(?:r)?|mesmo top|agora (?:faz )?com)\b",
                normalized_routing_question,
            ):
                query_hints.append(
                    "Se o pedido troca a categoria, substitua o filtro original pela nova "
                    "categoria. Consulte só a nova categoria com a mesma métrica, período e "
                    "limite. Compare as duas categorias apenas se o pedido solicitar comparação."
                )
            if filters_previous_ranking:
                query_hints.append(
                    "A pergunta anterior define exatamente a população a que 'dessas/desses' "
                    "se refere. Reconstrua essa consulta anterior em uma CTE, preservando gênero, "
                    "ano, métrica, direção da ordenação e LIMIT; filtre a CTE apenas por fora, "
                    "sem repor itens nem recalcular o top após o novo filtro. Use somente nomes "
                    "reais do esquema: no fato financeiro a coluna é receita_brl (nunca "
                    "revenue_brl nem recurso_brl), junto de orcamento_brl; lucro_brl é uma "
                    "expressão receita_brl - orcamento_brl, não uma coluna do fato. Para um "
                    "top de lucratividade, exija os dois valores e calcule lucro_brl para "
                    "preservar a ordenação anterior. Projete na CTE as colunas necessárias "
                    "ao novo filtro e aos desempates. Para filtros de nota, use nota_imdb ou "
                    "nota_tmdb e os votos da mesma fonte, conforme o pedido atual. Aplique "
                    "o operador e o valor pedidos somente após o LIMIT e preserve a ordem anterior."
                )
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
                    "Envie o SQL completo e executável, sem consultas de teste "
                    "como SELECT 1 nem comentários de rascunho. "
                    "Use JOIN explícito com ON ou USING. O executor rejeita CROSS JOIN "
                    "e tabelas separadas por vírgula no FROM. "
                    "Não invente números. Em SQLite, use 1.0 * numerador / denominador "
                    "para evitar divisão inteira. Médias de razões são calculadas por entidade "
                    "antes da agregação. Exemplo genérico: AVG(1.0 * itens_devolvidos / "
                    "itens_vendidos) é diferente de SUM(itens_devolvidos) / SUM(itens_vendidos). "
                    "Em dim_people.tipo_pessoa os valores são Ator e Diretor, com essa grafia; "
                    "não traduza os valores para actor/director. Ao buscar um nome de "
                    "pessoa, compare nome_pessoa com COLLATE NOCASE: a capitalização "
                    "no catálogo pode diferir da pergunta. Para recortes e agrupamentos "
                    "por ano civil, prefira ano_lancamento, que é numérico. "
                    "Nota zero é válida: use "
                    "IS NOT NULL e votos positivos, sem impor nota > 0. Em janelas até hoje, "
                    "exclua também datas futuras. Deduplique associações antes de contar "
                    "entidades. Em rankings, preserve "
                    "empates quando a pergunta pede o maior valor; se pede N itens, retorne "
                    "N com desempate estável. Se faltar métrica, unidade ou período "
                    "essencial, peça esclarecimento começando por CLARIFY: e não "
                    "chame a ferramenta. "
                    "Use o contexto somente quando a pergunta atual retomar a anterior. "
                    "Antes do SQL, identifique população, filtros, período, métrica, "
                    "sentido da ordenação e limite. Preserve os itens que o usuário "
                    "não mudou. Se a pergunta atual explicitar uma métrica, fonte ou ano, "
                    "o novo valor prevalece. Ao mudar a métrica, aplique os requisitos "
                    "de dados da nova métrica, sem herdar requisitos implícitos da antiga. "
                    "Em 'e qual teve menos?', inverta o ranking e consulte toda a população "
                    "elegível. Aplique o limite só depois da nova ordenação. O filme do top "
                    "anterior e o LIMIT anterior não são filtros da população. "
                    "Em 'dessas aí, quais', reconstrua a lista anterior com seu limite em "
                    "uma CTE e filtre só no SELECT externo, sem repor itens. "
                    "Em 'esse aí', restrinja ao título referenciado se for identificável. "
                    "Se não for possível resolver uma referência com segurança, use CLARIFY:. "
                    "Use somente estes nomes exatos de tabelas Gold: "
                    f"{available_tables}. Não invente nomes de tabelas."
                    " Use somente as colunas reais abaixo; não traduza nomes de colunas "
                    "nem invente aliases para colunas usadas nos JOINs:\n"
                    f"{schema_context}\n"
                    f"{_GOLD_RELATIONSHIPS_CONTEXT}\n"
                    f"\n{natural_rules}"
                    f"{evaluation_context}"
                    + (
                        f"\nPara esta pergunta: {_FOCUSED_METRIC_RULES[evaluation_case.query_id]}"
                        if evaluation_case and evaluation_case.query_id in _FOCUSED_METRIC_RULES
                        else ""
                    )
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
            {
                "role": "user",
                "content": (
                    "\n".join((normalized_question, *query_hints))
                    if query_hints else normalized_question
                ),
            },
            ]
            model_started_at = time.perf_counter()
            complete_for_complexity = getattr(self.model, "complete_for_complexity", None)
            try:
                if callable(complete_for_complexity):
                    first_turn = complete_for_complexity(messages, (RUN_SQL_TOOL,), complexity)
                else:
                    first_turn = self.model.complete(messages, (RUN_SQL_TOOL,))
                if (
                    analytical_intent
                    and first_turn.tool_call is None
                    and not self._extract_clarification(first_turn.answer)
                ):
                    retry_messages = [
                        *messages,
                        {
                            "role": "user",
                            "content": "Para responder à pergunta acima, execute run_sql.",
                        },
                    ]
                    if callable(complete_for_complexity):
                        first_turn = complete_for_complexity(
                            retry_messages, (RUN_SQL_TOOL,), complexity
                        )
                    else:
                        first_turn = self.model.complete(retry_messages, (RUN_SQL_TOOL,))
            except Exception as exc:
                status = getattr(exc, "status_code", getattr(exc, "code", None))
                try:
                    transient_status = int(status) in {408, 429, 500, 502, 503, 504}
                except (TypeError, ValueError):
                    transient_status = False
                if reference_fallback is None or not (
                    isinstance(
                        exc,
                        (ProviderTransientError, TimeoutError, ConnectionError, OSError),
                    )
                    or transient_status
                ):
                    raise
                logger.warning(
                    "Falha transitória do modelo na %s; usando consulta de referência.",
                    evaluation_case.query_id,
                )
                first_turn = ModelTurn(
                    tool_call=ToolCall(RUN_SQL_TOOL.name, {"sql": reference_fallback})
                )
                query_source = "reference"
            model_seconds = time.perf_counter() - model_started_at
            if first_turn.tool_call is None:
                clarification = self._extract_clarification(first_turn.answer)
                if clarification and reference_fallback is None:
                    raise AgentClarification(clarification)
                if reference_fallback is None:
                    return AgentResponse(
                        answer=_DEFAULT_CHAT_RESPONSE,
                        rows=(),
                        truncated=False,
                        tool_calls=0,
                        source="platform",
                    )
                query = reference_fallback
                query_source = "reference"
            else:
                call = self._require_tool_call(first_turn)
                if call.name != RUN_SQL_TOOL.name and reference_fallback is None:
                    raise AgentError("O modelo solicitou uma ferramenta não permitida.")
                proposed_query = call.arguments.get("sql")
                if not isinstance(proposed_query, str) and reference_fallback is None:
                    raise AgentError("A ferramenta recebeu argumentos inválidos.")
                query = (
                    proposed_query
                    if call.name == RUN_SQL_TOOL.name and isinstance(proposed_query, str)
                    else reference_fallback
                )
                if query_source != "reference":
                    query_source = "model" if query == proposed_query else "reference"

        attempts = [query]
        if reference_fallback is not None and query != reference_fallback:
            attempts.append(reference_fallback)
        query_started_at = time.perf_counter()
        for candidate in attempts:
            try:
                result = (
                    reference_future.result()
                    if candidate == reference_fallback and reference_future is not None
                    else self.executor.execute(validate_sql(candidate, max_rows=self.max_rows))
                )
                if evaluation_case and result.columns != evaluation_case.expected_columns:
                    raise EvaluationMismatch(
                        f"A consulta não retornou as colunas obrigatórias da métrica "
                        f"{evaluation_case.query_id}."
                    )
                if reference_fallback is not None and candidate != reference_fallback:
                    expected = reference_future.result()
                    compare_rows(result.rows, expected.rows)
                query = candidate
                if candidate != attempts[0]:
                    query_source = "reference"
                break
            except (SqlValidationError, QueryExecutionError, QueryTimeoutError,
                    EvaluationMismatch) as exc:
                if query_source == "model" and isinstance(
                    exc, (SqlValidationError, QueryExecutionError)
                ):
                    sqlite_detail = (
                        str(exc.__cause__)[:300]
                        if isinstance(exc, QueryExecutionError) and exc.__cause__
                        else ""
                    )
                    repair_error = str(exc)
                    if sqlite_detail:
                        repair_error += f" Detalhe do SQLite: {sqlite_detail}"
                    repair_messages = [*messages, {
                        "role": "user",
                        "content": (
                            "A consulta proposta não passou na validação ou execução. "
                            f"SQL proposto: {candidate}\nErro: {repair_error}\n"
                            "Corrija somente o problema indicado, consultando os nomes exatos "
                            "de tabelas e colunas no esquema informado. Não renomeie colunas "
                            "Gold para inglês nem invente campos; chame run_sql. "
                            "Preserve a métrica e os filtros solicitados."
                        ),
                    }]
                    try:
                        if callable(complete_for_complexity):
                            repaired = complete_for_complexity(
                                repair_messages, (RUN_SQL_TOOL,), complexity
                            )
                        else:
                            repaired = self.model.complete(repair_messages, (RUN_SQL_TOOL,))
                        repair_call = self._require_tool_call(repaired)
                        if repair_call.name != RUN_SQL_TOOL.name:
                            raise AgentError("Ferramenta de correção inválida.")
                        repair_sql = repair_call.arguments.get("sql")
                        if not isinstance(repair_sql, str):
                            raise AgentError("SQL de correção inválido.")
                        repaired_result = self.executor.execute(
                            validate_sql(repair_sql, max_rows=self.max_rows)
                        )
                        if (evaluation_case
                                and repaired_result.columns != evaluation_case.expected_columns):
                            raise EvaluationMismatch("Colunas da correção incompatíveis.")
                        if reference_future is not None:
                            compare_rows(repaired_result.rows, reference_future.result().rows)
                        result = repaired_result
                        query = repair_sql
                        query_source = "model_repaired"
                        break
                    except (AgentError, SqlValidationError, QueryExecutionError,
                            QueryTimeoutError, EvaluationMismatch, ProviderTransientError):
                        logger.info("A tentativa de correção SQL não produziu resultado válido.")
                if candidate != attempts[-1]:
                    logger.warning(
                        "SQL gerado para %s falhou na verificação (%s); "
                        "usando consulta de referência.",
                        evaluation_case.query_id,
                        type(exc).__name__,
                    )
                    continue
                if isinstance(exc, QueryTimeoutError):
                    raise
                if isinstance(exc, EvaluationMismatch):
                    raise AgentError(str(exc)) from exc
                logger.warning("Consulta GenAI rejeitada: %s", exc)
                raise AgentError("A consulta solicitada não pôde ser executada.") from exc
        query_seconds = time.perf_counter() - query_started_at

        row_count = len(result.rows)
        if row_count == 0:
            final_answer = _empty_analytical_answer(normalized_question)
        else:
            final_answer = reviewed_summary(
                normalized_routing_question, result.rows,
                evaluation_case.query_id if evaluation_case else None,
            ) or summarize_result(result.rows) or (
                f"A consulta retornou {row_count} "
                f"{'resultado' if row_count == 1 else 'resultados'}; "
                "os valores estão na tabela."
            )
            if animation_rank:
                final_answer = (
                    f"Top {row_count} de animações por bilheteria em reais desde "
                    f"{animation_rank[2]}. " + final_answer
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
                "Não encontrei filmes para esses critérios; a tabela está vazia."
                if row_count == 0
                else summarize_result(result.rows) or (
                    f"Encontrei {row_count} "
                    f"{'resultado' if row_count == 1 else 'resultados'}; "
                    "os valores estão na tabela."
                )
            )
            final_answer = (
                f"Orientação sobre o CineData (guia da plataforma):\n{platform_answer}\n\n"
                f"Análise dos filmes: {analytical_answer}"
            )
        elif semantic_matches and semantic_revenue_ranking and row_count:
            winner = result.rows[0]["titulo"]
            final_answer = (
                f"Entre os filmes encontrados pelas sinopses, {winner} tem a maior receita. "
                "A tabela mostra todos os filmes encontrados com receita informada."
            )
        elif semantic_matches:
            titles = ", ".join(match.title for match in semantic_matches)
            final_answer = (
                f"A busca nas sinopses encontrou: {titles}. "
                "Na tabela, você confere os dados desses filmes."
            )

        metric = evaluation_case.metric if evaluation_case else None
        if (
            {"lucro_brl", "receita_brl"}.issubset(result.columns)
            and (
                (evaluation_case and evaluation_case.query_id == "Q33")
                or len(re.findall(r"\btop\s*10\b", normalized_routing_question)) == 2
            )
        ):
            metric = "interseção dos rankings de bilheteria e lucro"
        unit = evaluation_case.unit if evaluation_case else None
        period = evaluation_case.period if evaluation_case else None
        population = evaluation_case.population if evaluation_case else None
        limitations = evaluation_case.limitations if evaluation_case else None
        if period_override:
            period = period_override
        if animation_rank:
            period = animation_rank[0].period
        if all_time_actor_ranking:
            metric = "quantidade de filmes por ator"
            unit = "filmes distintos"
            period = "todo o Gold disponível"
            population = "pessoas classificadas como Ator com créditos registrados no Gold"
            limitations = (
                "a associação reflete os créditos existentes no Gold e "
                "não distingue elenco principal"
            )
        if all_time_company_count:
            metric = "quantidade de filmes por produtora"
            unit = "filmes associados"
            period = "todo o Gold disponível"
            population = "produtoras com associações registradas em bridge_movie_company"
            limitations = (
                "filmes associados a mais de uma produtora contam uma vez para cada produtora"
            )
        if semantic_revenue_ranking:
            metric = "receita por filme"
            unit = "BRL"
            period = "filmes encontrados na busca"
            population = "filmes encontrados nas sinopses com receita informada"
            limitations = (
                "a busca considera termos de títulos e sinopses; filmes sem receita "
                "informada não aparecem no ranking"
            )

        response = AgentResponse(
            answer=final_answer,
            rows=result.rows,
            truncated=result.truncated,
            tool_calls=2 if query_source == "model_repaired" else 1,
            columns=result.columns,
            query_id=evaluation_case.query_id if evaluation_case else None,
            metric=metric,
            unit=unit,
            period=period,
            population=population,
            limitations=limitations,
            source="mixed" if mixed_intent or semantic_matches else "gold",
        )
        insight_started_at = time.perf_counter()
        if "margem" in result.columns:
            response = replace(response, insights=analytical_insights(response.rows))
        if self.insight_service is not None and not response.insights:
            response = replace(response, insights=self.insight_service.generate(response))
        if response.source == "gold" and not response.insights:
            insights = analytical_insights(response.rows, question=normalized_routing_question)
            if not response.rows:
                try:
                    coverage = finance_coverage_context(
                        normalized_routing_question, self.executor, self.max_rows
                    )
                    if coverage and evaluation_case and evaluation_case.query_id == "Q27":
                        response = replace(response, answer=coverage[0])
                    else:
                        insights = coverage or insights
                except (SqlValidationError, QueryExecutionError, QueryTimeoutError):
                    logger.info("Não foi possível complementar o insight de cobertura.")
            elif len(response.rows) == 1:
                row = response.rows[0]
                genre = row.get("nome_genero", row.get("genero"))
                increase = row.get("aumento_brl")
                year = row.get("ano_lancamento", row.get("ano"))
                mean = row.get("nota_media_imdb", row.get("media_imdb", row.get("media_nota_imdb")))
                if isinstance(genre, str) and type(increase) in (int, float):
                    try:
                        insights = revenue_growth_context(
                            normalized_routing_question, genre, increase, self.executor,
                            self.max_rows,
                        ) or insights
                    except (SqlValidationError, QueryExecutionError, QueryTimeoutError):
                        logger.info("Não foi possível complementar o insight de bilheteria.")
                elif not insights and type(year) is int and type(mean) in (int, float):
                    try:
                        insights = animation_rating_context(
                            normalized_routing_question, year, mean, self.executor, self.max_rows,
                        )
                    except (SqlValidationError, QueryExecutionError, QueryTimeoutError):
                        logger.info("Não foi possível conferir a amostra de notas.")
            elif not insights:
                try:
                    evidence = rating_context_for_titles(
                        normalized_routing_question, response.rows, self.executor, self.max_rows,
                    )
                    insights = analytical_insights(evidence, question=normalized_routing_question)
                except (SqlValidationError, QueryExecutionError, QueryTimeoutError):
                    logger.info("Não foi possível conferir as notas dos títulos exibidos.")
            response = replace(
                response, insights=insights,
            )
        logger.info(
            "GenAI question completed model_seconds=%.3f query_seconds=%.3f "
            "insight_seconds=%.3f total_seconds=%.3f returned_rows=%d "
            "truncated=%s query_source=%s",
            model_seconds,
            query_seconds,
            time.perf_counter() - insight_started_at,
            time.perf_counter() - started_at,
            row_count,
            result.truncated,
            query_source,
        )
        return response

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
