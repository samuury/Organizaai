"""Regras de negócio de autenticação, hashing de senhas e geração de JWT."""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.audit.service import registrar_auditoria
from app.modules.auth.models import User
from app.modules.auth.schemas import UsuarioCadastroEntrada, UsuarioLoginEntrada


class EmailJaCadastradoError(ValueError):
	"""Indica que o e-mail informado já pertence a outra conta."""


class CredenciaisInvalidasError(ValueError):
	"""Indica que o e-mail ou a senha não conferem."""


def gerar_hash_senha(senha: str) -> str:
	"""Gera o hash da senha utilizando bcrypt."""
	return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
	"""Compara a senha em texto com o hash armazenado."""
	try:
		return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
	except Exception:
		return False


def criar_token_jwt(
	usuario_id: int, perfil: str, nome: str, expira_em_minutos: int = 1440
) -> str:
	"""Gera token JWT contendo id do usuário, perfil e nome."""
	agora = datetime.now(timezone.utc)
	payload = {
		"sub": str(usuario_id),
		"perfil": perfil,
		"nome": nome,
		"iat": agora,
		"exp": agora + timedelta(minutes=expira_em_minutos),
	}
	return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def decodificar_token_jwt(token: str) -> dict[str, Any]:
	"""Decodifica e valida a assinatura e expiração do token JWT."""
	return jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])


def cadastrar_usuario(
	session: Session, dados: UsuarioCadastroEntrada, ip: str | None = None
) -> tuple[User, str]:
	"""Cadastra um novo usuário e retorna o usuário persistido com seu token."""
	email_normalizado = dados.email.lower().strip()
	usuario_existente = session.scalar(
		select(User).where(func.lower(User.email) == email_normalizado)
	)
	if usuario_existente is not None:
		raise EmailJaCadastradoError("Este e-mail já está em uso por outra conta.")

	usuario = User(
		nome=dados.nome.strip(),
		email=email_normalizado,
		senha_hash=gerar_hash_senha(dados.senha),
		perfil=dados.perfil,
	)
	session.add(usuario)
	session.flush()

	registrar_auditoria(
		session,
		usuario_id=usuario.id,
		acao="auth.cadastro",
		entidade="users",
		entidade_id=usuario.id,
		dados_depois={"nome": usuario.nome, "email": usuario.email, "perfil": usuario.perfil},
		ip=ip,
	)
	session.commit()
	token = criar_token_jwt(usuario.id, usuario.perfil, usuario.nome)
	return usuario, token


def autenticar_usuario(
	session: Session, dados: UsuarioLoginEntrada, ip: str | None = None
) -> tuple[User, str]:
	"""Autentica o usuário por e-mail e senha, registrando a tentativa em auditoria."""
	email_normalizado = dados.email.lower().strip()
	usuario = session.scalar(
		select(User).where(func.lower(User.email) == email_normalizado)
	)

	if usuario is None or not verificar_senha(dados.senha, usuario.senha_hash):
		registrar_auditoria(
			session,
			usuario_id=usuario.id if usuario else None,
			acao="auth.login_falha",
			entidade="users",
			dados_depois={"email": email_normalizado},
			ip=ip,
		)
		session.commit()
		raise CredenciaisInvalidasError("E-mail ou senha incorretos.")

	registrar_auditoria(
		session,
		usuario_id=usuario.id,
		acao="auth.login_sucesso",
		entidade="users",
		entidade_id=usuario.id,
		ip=ip,
	)
	session.commit()
	token = criar_token_jwt(usuario.id, usuario.perfil, usuario.nome)
	return usuario, token


def buscar_usuarios(
	session: Session,
	perfil: str | None = None,
	busca: str | None = None,
	limite: int = 50,
) -> list[User]:
	"""Pesquisa usuários cadastrados para seleção em interfaces de consentimento e emissão."""
	stmt = select(User)
	if perfil:
		stmt = stmt.where(User.perfil == perfil.upper())
	if busca and busca.strip():
		termo = f"%{busca.strip()}%"
		stmt = stmt.where(User.nome.ilike(termo) | User.email.ilike(termo))
	stmt = stmt.order_by(User.nome.asc()).limit(min(limite, 100))
	return list(session.scalars(stmt).all())
