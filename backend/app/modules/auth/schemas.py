"""Schemas Pydantic para o módulo de autenticação."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PerfilTipo = Literal["CIDADAO", "INSTITUICAO", "EMPRESA"]
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class UsuarioCadastroEntrada(BaseModel):
	"""Dados de entrada para cadastro de nova conta."""

	nome: str = Field(min_length=2, max_length=255)
	email: str = Field(pattern=EMAIL_PATTERN, min_length=5, max_length=255)
	senha: str = Field(min_length=8, max_length=128)
	perfil: PerfilTipo


class UsuarioLoginEntrada(BaseModel):
	"""Dados de entrada para autenticação."""

	email: str = Field(pattern=EMAIL_PATTERN, min_length=5, max_length=255)
	senha: str = Field(min_length=1, max_length=128)


class UsuarioResposta(BaseModel):
	"""Dados públicos de um usuário."""

	model_config = ConfigDict(from_attributes=True)

	id: int
	nome: str
	email: str
	perfil: PerfilTipo


class SessaoResposta(BaseModel):
	"""Token de acesso e dados do usuário logado."""

	access_token: str
	token_type: Literal["bearer"] = "bearer"
	usuario: UsuarioResposta
