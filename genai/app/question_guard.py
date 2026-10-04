"""Regras de entrada para manter o chatbot no escopo do CineData."""

import re
import unicodedata

_PROMPT_INJECTION = re.compile(
    r"\b(?:ignore|ignore as|desconsidere|desobedeca|bypass|contorne)\b.{0,80}"
    r"\b(?:instruc\w*|regra|prompt|sistema|system)\b|"
    r"\b(?:mostre|revele|exiba|repita)\b.{0,80}"
    r"\b(?:prompt|instruc\w*|sistema|system)\b",
    re.IGNORECASE,
)
_EXTERNAL_SOURCE = re.compile(
    r"\b(?:pesquise|busque|consulte|acesse|abra|navegue|procure)\b.{0,80}"
    r"\b(?:internet|web|google|wikipedia|site externo|url|http)\b|"
    r"\bhttps?://",
    re.IGNORECASE,
)
_RAW_SQL = re.compile(
    r"\b(?:execute|rode|run|envie)\b.{0,40}\b(?:sql|select|pragma|attach|insert|"
    r"update|delete|drop)\b|\b(?:pragma|attach|insert|update|delete|drop)\s+\w+",
    re.IGNORECASE,
)

_REJECTION_MESSAGE = (
    "Posso ajudar com recursos do CineData e dados do catálogo. "
    "Reformule a pergunta sem comandos SQL, instruções do sistema ou fontes externas."
)


def _normalize(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFD", value)
        if unicodedata.category(character) != "Mn"
    )


def rejection_message(question: str) -> str | None:
    """Returns a safe message when an input is outside the chatbot contract."""

    normalized = _normalize(question.casefold())
    if (
        _PROMPT_INJECTION.search(normalized)
        or _EXTERNAL_SOURCE.search(normalized)
        or _RAW_SQL.search(normalized)
    ):
        return _REJECTION_MESSAGE
    return None
