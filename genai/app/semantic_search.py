"""Busca local por significado aproximado em títulos e sinopses autorizadas."""

import math
import re
import threading
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass

from app.errors import GoldUnavailableError
from app.gold_database import GoldDatabase

_STOP_WORDS = frozenset(
    {
        "com",
        "como",
        "dos",
        "das",
        "em",
        "para",
        "por",
        "que",
        "uma",
        "um",
        "sobre",
        "filme",
        "filmes",
        "onde",
        "quando",
        "de",
        "do",
        "da",
        "e",
        "o",
        "a",
    }
)

# Palavras que ajudam a formular a pergunta, mas não descrevem o enredo. Elas
# não devem trazer candidatos por coincidirem com títulos ou sinopses.
_QUERY_STOP_WORDS = _STOP_WORDS | frozenset(
    {
        "diga",
        "exemplo",
        "historia",
        "historias",
        "maior",
        "maiores",
        "nota",
        "notas",
        "qual",
        "quais",
        "receita",
        "lucro",
        "orcamento",
        "tem",
        "tenha",
        "tenham",
        "teve",
        "valor",
        "brl",
        "usd",
    }
)


@dataclass(frozen=True)
class SemanticResult:
    movie_id: str
    title: str
    synopsis: str
    score: float


class SynopsisSearchIndex:
    """Índice leve, reconstruído quando a revisão local do Gold muda."""

    def __init__(self, database: GoldDatabase) -> None:
        self.database = database
        self._revision: tuple[int, int] | None = None
        self._documents: dict[str, tuple[str, str, Counter[str]]] = {}
        self._postings: dict[str, set[str]] = defaultdict(set)
        self._refresh_lock = threading.Lock()

    def search(self, question: str, limit: int = 5) -> tuple[SemanticResult, ...]:
        self._refresh_if_needed()
        with self._refresh_lock:
            documents = self._documents
            postings = self._postings
        terms = _query_tokens(question)
        if not terms:
            return ()
        candidates = set().union(*(postings.get(term, set()) for term in terms))
        if not candidates:
            return ()
        query = Counter(terms)
        scored: list[SemanticResult] = []
        for movie_id in candidates:
            title, synopsis, document = documents[movie_id]
            score = _cosine(query, document)
            if score:
                scored.append(SemanticResult(movie_id, title, synopsis, score))
        return tuple(
            sorted(scored, key=lambda result: (-result.score, result.title.casefold()))[:limit]
        )

    def _refresh_if_needed(self) -> None:
        with self._refresh_lock:
            try:
                stat = self.database.path.stat()
            except OSError as exc:
                raise GoldUnavailableError("A base de filmes não está acessível.") from exc
            revision = (stat.st_size, stat.st_mtime_ns)
            if revision == self._revision:
                return
            documents: dict[str, tuple[str, str, Counter[str]]] = {}
            postings: dict[str, set[str]] = defaultdict(set)
            with self.database.connect() as connection:
                rows = connection.execute(
                    "SELECT sk_movie_id, titulo, COALESCE(sinopse, '') FROM dim_movies "
                    "WHERE sinopse IS NOT NULL AND TRIM(sinopse) <> ''"
                ).fetchall()
            for movie_id, title, synopsis in rows:
                terms = Counter(_tokens(f"{title} {synopsis}"))
                if not terms:
                    continue
                key = str(movie_id)
                documents[key] = (str(title), str(synopsis), terms)
                for term in terms:
                    postings[term].add(key)
            self._documents = documents
            self._postings = postings
            self._revision = revision


def _tokens(text: str) -> tuple[str, ...]:
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFD", text.casefold())
        if unicodedata.category(character) != "Mn"
    )
    return tuple(
        token for token in re.findall(r"[a-z0-9]{3,}", normalized) if token not in _STOP_WORDS
    )


def _query_tokens(text: str) -> tuple[str, ...]:
    """Extrai somente os termos que descrevem o filme procurado."""

    normalized = "".join(
        character
        for character in unicodedata.normalize("NFD", text.casefold())
        if unicodedata.category(character) != "Mn"
    )
    return tuple(
        token
        for token in re.findall(r"[a-z0-9]{3,}", normalized)
        if token not in _QUERY_STOP_WORDS
    )


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    shared = set(left) & set(right)
    numerator = sum(left[term] * right[term] for term in shared)
    denominator = math.sqrt(sum(value * value for value in left.values())) * math.sqrt(
        sum(value * value for value in right.values())
    )
    return numerator / denominator if denominator else 0.0
