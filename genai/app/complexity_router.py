"""Classificação local da complexidade antes de qualquer chamada ao provedor."""

import re
import unicodedata
from enum import StrEnum


class QuestionComplexity(StrEnum):
    """Rotas que determinam o modelo principal quando ele é necessário."""

    SIMPLE = "simple"
    ANALYTICAL = "analytical"
    HYBRID = "hybrid"
    COMPLEX = "complex"


_ANALYTICAL_TERMS = re.compile(
    r"\b(?:filmes?|catalogo|receita|orcamento|lucro|margem|nota|imdb|tmdb|"
    r"popularidade|generos?|ator(?:es)?|diretor(?:es)?|produtora(?:s)?|"
    r"avaliacoes?|quantos?|maior(?:es)?|menor(?:es)?|media|ranking|ano)\b"
)
_SYNOPSIS_TERMS = re.compile(
    r"\b(?:sinopse|historia|enredo|tema|trama|sobre um filme|filme sobre)\b"
)
_COMPLEX_TERMS = re.compile(
    r"\b(?:compare|comparar|comparacao|relacao|relacione|cruze|cruzar|"
    r"correlacao|tendencia|evolucao|variacao|diferenca entre|ao longo|"
    r"por ano|por genero|por produtora|alem disso|tambem)\b"
)
_SIMPLE_TERMS = re.compile(
    r"\b(?:oi|ola|tudo bem|obrigad[oa]|ajuda|cinedata|plataforma|"
    r"comunidades?|listas?|amigos?|mapa de gostos)\b"
)


def classify_question(question: str, *, has_context: bool = False) -> QuestionComplexity:
    """Classifica pelo texto, sem modelo, I/O ou retenção da pergunta.

    A classificação não altera guardrails nem a escolha de consultas locais; ela
    só decide qual modelo principal é usado quando a pergunta precisa de SQL
    gerado pelo provedor.
    """

    normalized = _normalize(question)
    analytical = bool(_ANALYTICAL_TERMS.search(normalized))
    descriptive = bool(_SYNOPSIS_TERMS.search(normalized))

    if analytical and descriptive:
        return QuestionComplexity.HYBRID
    if has_context or len(normalized.split()) >= 24 or _COMPLEX_TERMS.search(normalized):
        return QuestionComplexity.COMPLEX if analytical else QuestionComplexity.SIMPLE
    if analytical:
        return QuestionComplexity.ANALYTICAL
    if _SIMPLE_TERMS.search(normalized):
        return QuestionComplexity.SIMPLE
    return QuestionComplexity.ANALYTICAL


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))
