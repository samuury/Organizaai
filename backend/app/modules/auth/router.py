"""Rotas de autenticação e consulta de usuários."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.models import User
from app.modules.auth.schemas import (
	SessaoResposta,
	UsuarioCadastroEntrada,
	UsuarioLoginEntrada,
	UsuarioResposta,
)
from app.modules.auth.service import (
	CredenciaisInvalidasError,
	EmailJaCadastradoError,
	autenticar_usuario,
	buscar_usuarios,
	cadastrar_usuario,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
	return request.client.host if request.client else None


@router.post("/register", response_model=SessaoResposta, status_code=201)
def registrar(
	dados: UsuarioCadastroEntrada,
	request: Request,
	session: Annotated[Session, Depends(get_db)],
) -> SessaoResposta:
	"""Cadastra um novo usuário e retorna o token de sessão."""
	try:
		usuario, token = cadastrar_usuario(session, dados, ip=_client_ip(request))
	except EmailJaCadastradoError as error:
		raise HTTPException(status_code=409, detail=str(error)) from error

	return SessaoResposta(
		access_token=token,
		token_type="bearer",
		usuario=UsuarioResposta.model_validate(usuario),
	)


@router.post("/login", response_model=SessaoResposta)
def login(
	dados: UsuarioLoginEntrada,
	request: Request,
	session: Annotated[Session, Depends(get_db)],
) -> SessaoResposta:
	"""Autentica o usuário por e-mail e senha."""
	try:
		usuario, token = autenticar_usuario(session, dados, ip=_client_ip(request))
	except CredenciaisInvalidasError as error:
		raise HTTPException(status_code=401, detail=str(error)) from error

	return SessaoResposta(
		access_token=token,
		token_type="bearer",
		usuario=UsuarioResposta.model_validate(usuario),
	)


@router.get("/me", response_model=UsuarioResposta)
def obter_usuario_logado(
	request: Request,
	session: Annotated[Session, Depends(get_db)],
) -> UsuarioResposta:
	"""Retorna os dados do usuário associado à sessão atual."""
	user_id = getattr(request.state, "user_id", None)
	if not isinstance(user_id, int) or user_id < 1:
		raise HTTPException(status_code=401, detail="Autenticação obrigatória.")
	usuario = session.get(User, user_id)
	if usuario is None:
		raise HTTPException(status_code=404, detail="Usuário não encontrado.")
	return UsuarioResposta.model_validate(usuario)


@router.get("/users", response_model=list[UsuarioResposta])
def listar_ou_buscar_usuarios(
	request: Request,
	session: Annotated[Session, Depends(get_db)],
	perfil: Annotated[str | None, Query(description="Filtrar por perfil (CIDADAO, INSTITUICAO, EMPRESA)")] = None,
	busca: Annotated[str | None, Query(description="Filtrar por nome ou e-mail")] = None,
	limite: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[UsuarioResposta]:
	"""Lista ou busca usuários para seleção de destinatários e empresas parceiras."""
	user_id = getattr(request.state, "user_id", None)
	if not isinstance(user_id, int) or user_id < 1:
		raise HTTPException(status_code=401, detail="Autenticação obrigatória.")
	usuarios = buscar_usuarios(session, perfil=perfil, busca=busca, limite=limite)
	return [UsuarioResposta.model_validate(u) for u in usuarios]
