"""Rotas autenticadas do histórico privado do chatbot."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationMessagesAppend,
    ConversationRead,
    ConversationUpdate,
)
from app.conversations.services import ConversationsService
from app.db.session import get_db
from app.users.dependencies import get_current_user
from app.users.models import User

conversations_router = APIRouter(prefix="/minha-conta/conversas", tags=["conversas"])


@conversations_router.get("", response_model=list[ConversationRead])
async def listar_conversas(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[ConversationRead]:
    return await ConversationsService(session).listar(user)


@conversations_router.post("", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
async def criar_conversa(
    data: ConversationCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ConversationDetail:
    return await ConversationsService(session).criar(data, user)


@conversations_router.get("/{conversation_id}", response_model=ConversationDetail)
async def obter_conversa(
    conversation_id: Annotated[str, Path(min_length=1, max_length=32)],
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ConversationDetail:
    return await ConversationsService(session).obter(conversation_id, user)


@conversations_router.patch("/{conversation_id}", response_model=ConversationRead)
async def atualizar_conversa(
    conversation_id: Annotated[str, Path(min_length=1, max_length=32)],
    data: ConversationUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ConversationRead:
    return await ConversationsService(session).atualizar(conversation_id, data, user)


@conversations_router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remover_conversa(
    conversation_id: Annotated[str, Path(min_length=1, max_length=32)],
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    await ConversationsService(session).remover(conversation_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@conversations_router.post("/{conversation_id}/mensagens", response_model=ConversationDetail)
async def anexar_mensagens(
    conversation_id: Annotated[str, Path(min_length=1, max_length=32)],
    data: ConversationMessagesAppend,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ConversationDetail:
    return await ConversationsService(session).anexar_mensagens(conversation_id, data, user)
