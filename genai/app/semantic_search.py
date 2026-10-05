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
        "algum",
        "alguma",
        "alguem",
        "diga",
        "encontre",
        "encontrar",
        "envolve",
        "envolvem",
        "exemplo",
        "historia",
        "historias",
        "maior",
        "maiores",
        "mostra",
        "mostram",
        "nota",
        "notas",
        "qual",
        "quais",
        "receita",
        "lucro",
        "orcamento",
        "personagem",
        "personagens",
        "pessoa",
        "pessoas",
        "precisa",
        "precisam",
        "tem",
        "tenha",
        "tenham",
        "teve",
        "tentando",
        "valor",
        "brl",
        "usd",
    }
)

_EMPTY_SYNOPSIS = frozenset(
    {
        "sem descricao",
        "no description",
        "no overview",
        "plot details unknown",
        "to be added later",
    }
)


@dataclass(frozen=True)
class SemanticResult:
    movie_id: str
    title: str
    synopsis: str
    score: float
    matched_terms: int = 0


class SynopsisSearchIndex:
    """Índice leve, reconstruído quando a revisão local do Gold muda."""

    def __init__(self, database: GoldDatabase) -> None:
        self.database = database
        self._revision: tuple[int, int] | None = None
        self._documents: dict[str, tuple[str, str, Counter[str]]] = {}
        self._postings: dict[str, set[str]] = defaultdict(set)
        self._refresh_lock = threading.Lock()

    def search(
        self, question: str, limit: int = 5, *, min_terms: int = 1
    ) -> tuple[SemanticResult, ...]:
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
        required = min(min_terms, len(set(terms)))
        scored: list[SemanticResult] = []
        for movie_id in candidates:
            title, synopsis, document = documents[movie_id]
            matched = len(set(terms) & document.keys())
            if matched < required:
                continue
            score = _cosine(query, document)
            if score:
                scored.append(SemanticResult(movie_id, title, synopsis, score, matched))
        return tuple(
            sorted(scored, key=lambda result: (-result.score, result.title.casefold()))[:limit]
        )

    def search_concepts(
        self, concepts: tuple[tuple[str, ...], ...], limit: int = 5
    ) -> tuple[SemanticResult, ...]:
        """Exige evidência textual para cada conceito, sem expor sinopses ao modelo."""

        self._refresh_if_needed()
        with self._refresh_lock:
            documents = self._documents
            postings = self._postings
        groups = tuple(
            frozenset(
                tokens[0]
                for term in group
                if len(tokens := _query_tokens(term)) == 1
            )
            for group in concepts
        )
        if len(groups) != len(concepts) or not groups:
            return ()
        duplicates = {
            term for term, count in Counter(term for group in groups for term in group).items()
            if count > 1
        }
        groups = tuple(group - duplicates for group in groups)
        if any(not group for group in groups):
            return ()
        group_candidates = tuple(
            set().union(*(postings.get(term, set()) for term in group))
            for group in groups
        )
        candidates = set.intersection(*group_candidates)
        if not candidates:
            return ()
        total_documents = len(documents)
        query_terms = set().union(*groups)
        scored: list[SemanticResult] = []
        for movie_id in candidates:
            title, synopsis, document = documents[movie_id]
            proximity = 0
            if len(groups) == 2:
                synopsis_terms = _tokens(synopsis)
                first_positions = (
                    position for position, term in enumerate(synopsis_terms)
                    if term in groups[0]
                )
                second_positions = [
                    position for position, term in enumerate(synopsis_terms)
                    if term in groups[1]
                ]
                proximity = min(
                    abs(first - second)
                    for first in first_positions for second in second_positions
                )
                if proximity > 14:
                    continue
            evidence = [
                max(
                    math.log((total_documents + 1) / (len(postings[term]) + 1)) + 1
                    for term in group & document.keys()
                )
                for group in groups
            ]
            score = sum(evidence) / (len(groups) * (1 + math.log1p(sum(document.values()))))
            if len(groups) == 2:
                score *= 1 + 0.5 / (1 + proximity)
            matched = len(set(document) & query_terms)
            scored.append(
                SemanticResult(movie_id, title, synopsis, score / (score + 3), matched)
            )
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
                if " ".join(_tokens(synopsis)) in _EMPTY_SYNOPSIS:
                    continue
                terms = Counter(_tokens(synopsis))
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
        _term_root(token)
        for token in re.findall(r"[a-z0-9]{3,}", normalized)
        if token not in _STOP_WORDS
    )


def _query_tokens(text: str) -> tuple[str, ...]:
    """Extrai somente os termos que descrevem o filme procurado."""

    normalized = "".join(
        character
        for character in unicodedata.normalize("NFD", text.casefold())
        if unicodedata.category(character) != "Mn"
    )
    return tuple(
        _term_root(token)
        for token in re.findall(r"[a-z0-9]{3,}", normalized)
        if token not in _QUERY_STOP_WORDS
    )


def _term_root(token: str) -> str:
    """Unifica plurais simples em perguntas e sinopses."""

    return token[:-1] if len(token) > 4 and token.endswith("s") else token


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    shared = set(left) & set(right)
    numerator = sum(left[term] * right[term] for term in shared)
    denominator = math.sqrt(sum(value * value for value in left.values())) * math.sqrt(
        sum(value * value for value in right.values())
    )
    return numerator / denominator if denominator else 0.0
