"""Schemas de requisição e resposta do chatbot assistente."""

from typing import Literal

from pydantic import BaseModel, Field


class MensagemChat(BaseModel):
	"""Mensagem individual no histórico de conversação."""

	role: Literal["user", "assistant"]
	content: str = Field(min_length=1, max_length=4000)


class EnviarMensagemEntrada(BaseModel):
	"""Mensagem do usuário e histórico prévio."""

	mensagem: str = Field(min_length=1, max_length=4000)
	historico: list[MensagemChat] = Field(default_factory=list)


class RespostaChat(BaseModel):
	"""Resposta gerada pelo assistente."""

	resposta: str
	modelo: str
