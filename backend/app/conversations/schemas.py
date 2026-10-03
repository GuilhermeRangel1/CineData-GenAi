"""Contratos HTTP do histórico privado do chatbot."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationCreate(BaseModel):
    """Dados opcionais para iniciar uma conversa salva."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    titulo: str = Field(default="Nova conversa", min_length=1, max_length=120)


class ConversationUpdate(BaseModel):
    """Permite renomear a conversa sem alterar as mensagens."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    titulo: str = Field(min_length=1, max_length=120)


class ConversationMessageCreate(BaseModel):
    """Mensagem já exibida ao usuário que deve integrar o histórico privado."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12_000)
    response_data: dict[str, Any] | None = None

    @field_validator("response_data")
    @classmethod
    def limitar_carga_estruturada(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None and len(str(value)) > 500_000:
            raise ValueError("A resposta estruturada excede o limite permitido.")
        return value


class ConversationMessagesAppend(BaseModel):
    """Anexa uma ou mais mensagens em ordem, normalmente pergunta e resposta."""

    model_config = ConfigDict(extra="forbid")

    mensagens: list[ConversationMessageCreate] = Field(min_length=1, max_length=2)


class ConversationMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: Literal["user", "assistant"]
    content: str
    response_data: dict[str, Any] | None
    created_at: datetime


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    titulo: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationRead):
    mensagens: list[ConversationMessageRead]
