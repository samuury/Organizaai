"""Rotas da API para o chatbot assistente com Claude Haiku."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.models import User
from app.modules.chat.schemas import EnviarMensagemEntrada, RespostaChat
from app.modules.chat.service import processar_mensagem_chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=RespostaChat)
async def enviar_mensagem(
	dados: EnviarMensagemEntrada,
	request: Request,
	session: Annotated[Session, Depends(get_db)],
) -> RespostaChat:
	"""Envia uma mensagem para o assistente e retorna a resposta gerada."""
	user_id = getattr(request.state, "user_id", None)
	usuario_nome: str | None = None
	usuario_perfil: str | None = None

	if isinstance(user_id, int) and user_id > 0:
		user = session.get(User, user_id)
		if user:
			usuario_nome = user.nome
			usuario_perfil = user.perfil

	resposta, modelo = await processar_mensagem_chat(
		mensagem=dados.mensagem,
		historico=dados.historico,
		usuario_nome=usuario_nome,
		usuario_perfil=usuario_perfil,
	)

	return RespostaChat(resposta=resposta, modelo=modelo)
