"""Contratos da conversa com o assistente de cinema."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MensagemChat(BaseModel):
    """Mensagem individual enviada pelo cliente."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    conteudo: str = Field(min_length=1, max_length=2000)


class ConversaChat(BaseModel):
    """Histórico limitado de uma conversa, sem persistência no banco."""

    model_config = ConfigDict(extra="forbid")

    mensagens: list[MensagemChat] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def validar_ordem_das_mensagens(self) -> "ConversaChat":
        if self.mensagens[0].role != "user":
            raise ValueError("A conversa deve começar com uma mensagem do usuário.")
        if self.mensagens[-1].role != "user":
            raise ValueError("A última mensagem deve ser do usuário.")
        if any(
            anterior.role == atual.role
            for anterior, atual in zip(self.mensagens, self.mensagens[1:])
        ):
            raise ValueError("As mensagens da conversa devem alternar entre usuário e assistente.")
        return self


class RespostaChat(BaseModel):
    """Resposta textual do modelo."""

    model_config = ConfigDict(extra="forbid")

    mensagem: str = Field(min_length=1, max_length=8000)
    modelo: str = Field(min_length=1, max_length=100)
