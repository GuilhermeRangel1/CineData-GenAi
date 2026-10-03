"""Modelo persistente de contas locais.

As contas são independentes dos dados importados do catálogo. Relações com
avaliações, listas e comunidades serão introduzidas em migrações próprias.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.movies.models import DimMovie

USER_ROLES: tuple[str, ...] = ("user", "admin")
LIST_VISIBILITIES: tuple[str, ...] = ("publica", "privada")
FRIENDSHIP_STATUSES: tuple[str, ...] = ("pendente", "aceita", "bloqueada")


user_list_movies = Table(
    "user_list_movies",
    Base.metadata,
    Column(
        "list_id",
        String(32),
        ForeignKey("user_lists.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "sk_movie_id",
        String(64),
        ForeignKey("dim_movies.sk_movie_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
)


watch_later_movies = Table(
    "watch_later_movies",
    Base.metadata,
    Column(
        "user_id",
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "sk_movie_id",
        String(64),
        ForeignKey("dim_movies.sk_movie_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
)


def generate_user_id() -> str:
    """Gera um identificador opaco para uma conta local."""

    return uuid4().hex


class User(Base):
    """Conta autenticável por e-mail e senha."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN (" + ", ".join(f"'{role}'" for role in USER_ROLES) + ")",
            name="role_valid",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_user_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(
        String(20),
        default="user",
        server_default="user",
        index=True,
    )
    avatar_url: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
    lists: Mapped[list["UserList"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="UserList.created_at.desc()"
    )
    conversations: Mapped[list["ChatConversation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="ChatConversation.updated_at.desc()",
    )


class UserList(Base):
    """Lista personalizada pertencente a uma única conta local."""

    __tablename__ = "user_lists"
    __table_args__ = (
        CheckConstraint(
            "visibilidade IN ("
            + ", ".join(f"'{visibility}'" for visibility in LIST_VISIBILITIES)
            + ")",
            name="visibility_valid",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_user_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    nome: Mapped[str] = mapped_column(String(120))
    visibilidade: Mapped[str] = mapped_column(
        String(20), default="privada", server_default="privada", index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="lists")
    movies: Mapped[list["DimMovie"]] = relationship(
        secondary=user_list_movies,
        order_by=user_list_movies.c.created_at.desc(),
    )


class FriendshipRequest(Base):
    """Pedido direcionado que pode virar amizade ou bloqueio."""

    __tablename__ = "friendship_requests"
    __table_args__ = (
        CheckConstraint("requester_id <> recipient_id", name="different_users"),
        CheckConstraint(
            "status IN ("
            + ", ".join(f"'{status}'" for status in FRIENDSHIP_STATUSES)
            + ")",
            name="status_valid",
        ),
        UniqueConstraint("requester_id", "recipient_id", name="requester_recipient_unique"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_user_id)
    requester_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    recipient_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pendente", server_default="pendente", index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# Registra o outro lado de ``User.conversations`` mesmo nos processos que usam
# somente modelos antigos, como a preparação de trailers no Docker Compose.
from app.conversations.models import ChatConversation  # noqa: E402, F401
