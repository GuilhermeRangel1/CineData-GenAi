"""Conversa autenticada com o assistente de cinema."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.chatbot.schemas import ConversaChat, RespostaChat
from app.chatbot.services import AssistenteCinemaService
from app.users.dependencies import get_current_user
from app.users.models import User

chatbot_router = APIRouter(prefix="/assistente", tags=["assistente"])


@chatbot_router.post("/mensagens", response_model=RespostaChat)
async def enviar_mensagem(
    conversa: ConversaChat,
    usuario: Annotated[User, Depends(get_current_user)],
) -> RespostaChat:
    """Responde ao histórico enviado pela conta autenticada sem armazená-lo."""

    del usuario
    return await AssistenteCinemaService().responder(conversa)
