"""Modelos persistentes do histórico privado do chatbot."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

CHAT_MESSAGE_ROLES: tuple[str, ...] = ("user", "assistant")


def generate_conversation_id() -> str:
    """Gera um identificador opaco para uma conversa privada."""

    return uuid4().hex


class ChatConversation(Base):
    """Conversa salva que pertence exclusivamente a uma conta autenticada."""

    __tablename__ = "chat_conversations"
    __table_args__ = (
        Index("ix_chat_conversations_user_updated_at", "user_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_conversation_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    titulo: Mapped[str] = mapped_column(
        String(120), default="Nova conversa", server_default="Nova conversa"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.position",
    )


class ChatMessage(Base):
    """Mensagem ordenada; a carga estruturada preserva tabelas e gráficos já exibidos."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN (" + ", ".join(f"'{role}'" for role in CHAT_MESSAGE_ROLES) + ")",
            name="role_valid",
        ),
        CheckConstraint("position >= 0", name="position_nao_negativa"),
        UniqueConstraint("conversation_id", "position", name="conversation_position_unique"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_conversation_id)
    conversation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("chat_conversations.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    response_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped[ChatConversation] = relationship(back_populates="messages")
