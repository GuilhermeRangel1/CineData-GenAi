"""Casos de uso do histórico privado de conversas."""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.conversations.models import ChatConversation, ChatMessage
from app.conversations.schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationMessageRead,
    ConversationMessagesAppend,
    ConversationRead,
    ConversationUpdate,
)
from app.core.errors import ConversationNotFoundError, FilmePersistenceError
from app.users.models import User

logger = logging.getLogger(__name__)


class ConversationsService:
    """Garante que uma conta só possa manipular suas próprias conversas."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def listar(self, user: User) -> list[ConversationRead]:
        conversations = await self._session.scalars(
            select(ChatConversation)
            .where(ChatConversation.user_id == user.id)
            .order_by(ChatConversation.updated_at.desc(), ChatConversation.id.desc())
        )
        return [self._to_read(conversation) for conversation in conversations]

    async def criar(self, data: ConversationCreate, user: User) -> ConversationDetail:
        conversation = ChatConversation(user_id=user.id, titulo=data.titulo)
        try:
            self._session.add(conversation)
            await self._session.commit()
            await self._session.refresh(conversation)
        except SQLAlchemyError as error:
            await self._session.rollback()
            logger.error("Criação de conversa interrompida por falha de persistência.")
            raise FilmePersistenceError from error
        return await self.obter(conversation.id, user)

    async def obter(self, conversation_id: str, user: User) -> ConversationDetail:
        return self._to_detail(await self._get_conversation(conversation_id, user.id))

    async def atualizar(
        self, conversation_id: str, data: ConversationUpdate, user: User
    ) -> ConversationRead:
        conversation = await self._get_conversation(conversation_id, user.id)
        try:
            conversation.titulo = data.titulo
            await self._session.commit()
            await self._session.refresh(conversation)
        except SQLAlchemyError as error:
            await self._session.rollback()
            logger.error("Atualização de conversa interrompida por falha de persistência.")
            raise FilmePersistenceError from error
        return self._to_read(conversation)

    async def remover(self, conversation_id: str, user: User) -> None:
        conversation = await self._get_conversation(conversation_id, user.id)
        try:
            await self._session.delete(conversation)
            await self._session.commit()
        except SQLAlchemyError as error:
            await self._session.rollback()
            logger.error("Remoção de conversa interrompida por falha de persistência.")
            raise FilmePersistenceError from error

    async def anexar_mensagens(
        self, conversation_id: str, data: ConversationMessagesAppend, user: User
    ) -> ConversationDetail:
        conversation = await self._get_conversation(conversation_id, user.id)
        initial_position = len(conversation.messages)
        try:
            conversation.messages.extend(
                ChatMessage(
                    position=initial_position + index,
                    role=message.role,
                    content=message.content,
                    response_data=message.response_data,
                )
                for index, message in enumerate(data.mensagens)
            )
            conversation.updated_at = datetime.now()
            await self._session.commit()
        except SQLAlchemyError as error:
            await self._session.rollback()
            logger.error("Gravação de mensagens interrompida por falha de persistência.")
            raise FilmePersistenceError from error
        return await self.obter(conversation_id, user)

    async def _get_conversation(self, conversation_id: str, user_id: str) -> ChatConversation:
        conversation = await self._session.scalar(
            select(ChatConversation)
            .where(ChatConversation.id == conversation_id, ChatConversation.user_id == user_id)
            .options(selectinload(ChatConversation.messages))
        )
        if conversation is None:
            raise ConversationNotFoundError
        return conversation

    @staticmethod
    def _to_read(conversation: ChatConversation) -> ConversationRead:
        return ConversationRead(
            id=conversation.id,
            titulo=conversation.titulo,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )

    @classmethod
    def _to_detail(cls, conversation: ChatConversation) -> ConversationDetail:
        return ConversationDetail(
            **cls._to_read(conversation).model_dump(),
            mensagens=[
                ConversationMessageRead(
                    id=message.id,
                    role=message.role,
                    content=message.content,
                    response_data=message.response_data,
                    created_at=message.created_at,
                )
                for message in conversation.messages
            ],
        )
