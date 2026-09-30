"""Integração do assistente com a API Gemini."""

import logging

import httpx

from app.chatbot.schemas import ConversaChat, RespostaChat
from app.core.config import get_settings
from app.core.errors import ErroDominio

logger = logging.getLogger(__name__)


class GeminiNaoConfiguradoError(ErroDominio):
    status_code = 503
    codigo = "GEMINI_NAO_CONFIGURADO"
    mensagem = "Configure GEMINI_API_KEY no backend para ativar o assistente."


class GeminiLimiteError(ErroDominio):
    status_code = 429
    codigo = "GEMINI_LIMITE_ATINGIDO"
    mensagem = "O assistente atingiu o limite temporário. Tente novamente em instantes."


class GeminiIndisponivelError(ErroDominio):
    status_code = 502
    codigo = "GEMINI_INDISPONIVEL"
    mensagem = "O assistente não conseguiu responder agora. Tente novamente."


class GeminiTempoLimiteError(ErroDominio):
    status_code = 504
    codigo = "GEMINI_TEMPO_LIMITE"
    mensagem = "A resposta demorou mais que o esperado. Tente novamente."


class AssistenteCinemaService:
    """Envia apenas o histórico informado para o modelo configurado."""

    _INSTRUCAO = (
        "Você é o assistente de cinema do CineData. Responda sempre em português brasileiro, "
        "com simpatia, clareza e concisão. Ajude com conversas sobre filmes, gêneros e uso do "
        "CineData. Você não tem acesso ao catálogo, às listas, ao perfil ou aos dados privados "
        "do usuário; não afirme que consultou essas informações e não invente disponibilidade, "
        "avaliações ou detalhes específicos. Se pedirem algo que dependa desses dados, explique "
        "essa limitação e oriente a pessoa a consultar a tela correspondente no CineData."
    )

    async def responder(self, conversa: ConversaChat) -> RespostaChat:
        settings = get_settings()
        if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value().strip():
            raise GeminiNaoConfiguradoError

        conteudos = [
            {
                "role": "model" if mensagem.role == "assistant" else "user",
                "parts": [{"text": mensagem.conteudo}],
            }
            for mensagem in conversa.mensagens
        ]
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": self._INSTRUCAO}]},
            "contents": conteudos,
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800},
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(40.0)) as client:
                resposta = await client.post(
                    url,
                    headers={"x-goog-api-key": settings.gemini_api_key.get_secret_value()},
                    json=payload,
                )
        except httpx.TimeoutException as error:
            raise GeminiTempoLimiteError from error
        except httpx.RequestError as error:
            logger.warning("Falha de conexão com Gemini: %s", type(error).__name__)
            raise GeminiIndisponivelError from error

        if resposta.status_code == 429:
            raise GeminiLimiteError
        if resposta.is_error:
            logger.warning("Gemini respondeu com status HTTP %s", resposta.status_code)
            raise GeminiIndisponivelError

        try:
            dados = resposta.json()
            partes = dados["candidates"][0]["content"]["parts"]
            texto = "\n".join(
                parte["text"]
                for parte in partes
                if isinstance(parte, dict)
                and not parte.get("thought")
                and isinstance(parte.get("text"), str)
            ).strip()
        except (KeyError, IndexError, TypeError, ValueError) as error:
            logger.warning("Gemini retornou uma resposta sem texto utilizável")
            raise GeminiIndisponivelError from error

        if not texto:
            raise GeminiIndisponivelError
        return RespostaChat(mensagem=texto, modelo=settings.gemini_model)
