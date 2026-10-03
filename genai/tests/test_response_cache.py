"""Testes do cache temporário de respostas."""

from pathlib import Path

from app.agent_models import AgentResponse, ConversationContext
from app.response_cache import ResponseCache, gold_version, make_cache_key


def _response() -> AgentResponse:
    return AgentResponse(answer="Resposta", rows=(), truncated=False, tool_calls=0)


def test_cache_key_changes_for_session_context_gold_and_rules(tmp_path: Path) -> None:
    database = tmp_path / "gold.db"
    database.write_bytes(b"SQLite format 3\x00")
    context = (ConversationContext(question="Qual a receita?", metric="receita"),)
    base = make_cache_key(
        conversation_id="session-123456",
        question="Qual é a receita?",
        context=context,
        gold_revision=gold_version(database),
        rules_version="1",
    )
    assert base != make_cache_key(
        conversation_id="session-654321",
        question="Qual é a receita?",
        context=context,
        gold_revision=gold_version(database),
        rules_version="1",
    )
    assert base != make_cache_key(
        conversation_id="session-123456",
        question="Qual é a receita?",
        context=(),
        gold_revision=gold_version(database),
        rules_version="1",
    )
    assert base != make_cache_key(
        conversation_id="session-123456",
        question="Qual é a receita?",
        context=context,
        gold_revision=gold_version(database),
        rules_version="2",
    )


def test_cache_returns_response_until_expiration() -> None:
    cache = ResponseCache(ttl_seconds=60)
    cache.put("key", _response())

    assert cache.get("key") == _response()


def test_cache_drops_expired_response() -> None:
    cache = ResponseCache(ttl_seconds=0)
    cache.put("key", _response())

    assert cache.get("key") is None
