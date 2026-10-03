"""Cache pequeno e em memória para respostas GenAI da sessão atual."""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from app.agent_models import AgentResponse, ConversationContext


@dataclass(frozen=True)
class CachedAnswer:
    response: AgentResponse
    expires_at: float


class ResponseCache:
    """Armazena respostas bem-sucedidas até expirar ou a chave mudar."""

    def __init__(self, ttl_seconds: float = 300.0, max_entries: int = 100) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[str, CachedAnswer] = {}
        self._lock = Lock()

    def get(self, key: str) -> AgentResponse | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= time.monotonic():
                self._entries.pop(key, None)
                return None
            return entry.response

    def put(self, key: str, response: AgentResponse) -> None:
        with self._lock:
            if len(self._entries) >= self.max_entries:
                oldest_key = next(iter(self._entries))
                self._entries.pop(oldest_key, None)
            self._entries[key] = CachedAnswer(response, time.monotonic() + self.ttl_seconds)


def gold_version(path: Path) -> str:
    """Identifica uma revisão local do Gold sem reler o banco inteiro."""

    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def make_cache_key(
    *,
    conversation_id: str,
    question: str,
    context: tuple[ConversationContext, ...],
    gold_revision: str,
    rules_version: str,
) -> str:
    """Cria uma chave estável sem armazenar o texto em claro como identificador."""

    payload = {
        "conversation_id": conversation_id,
        "question": " ".join(question.casefold().split()),
        "context": [
            {
                "question": " ".join(turn.question.casefold().split()),
                "metric": turn.metric,
                "unit": turn.unit,
                "period": turn.period,
                "population": turn.population,
            }
            for turn in context
        ],
        "gold_revision": gold_revision,
        "rules_version": rules_version,
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
