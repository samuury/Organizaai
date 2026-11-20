"""Testes unitários e de integração do módulo de autenticação."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.auth.models import User
from app.modules.auth.schemas import UsuarioCadastroEntrada, UsuarioLoginEntrada
from app.modules.auth.service import (
	CredenciaisInvalidasError,
	EmailJaCadastradoError,
	autenticar_usuario,
	buscar_usuarios,
	cadastrar_usuario,
	criar_token_jwt,
	decodificar_token_jwt,
	gerar_hash_senha,
	verificar_senha,
)


def _setup_test_db():
	engine = create_engine(
		"sqlite://",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	AuditLog.__table__.create(engine)
	User.__table__.create(engine)
	return sessionmaker(bind=engine, expire_on_commit=False)


def test_hashing_senha_bcrypt() -> None:
	senha = "senha_super_secreta_123"
	hash_gerado = gerar_hash_senha(senha)
	assert hash_gerado != senha
	assert verificar_senha(senha, hash_gerado)
	assert not verificar_senha("senha_errada", hash_gerado)


def test_geracao_e_decodificacao_jwt() -> None:
	token = criar_token_jwt(usuario_id=42, perfil="CIDADAO", nome="Maria Cidadã")
	payload = decodificar_token_jwt(token)
	assert payload["sub"] == "42"
	assert payload["perfil"] == "CIDADAO"
	assert payload["nome"] == "Maria Cidadã"


def test_cadastro_usuario_service() -> None:
	session_factory = _setup_test_db()
	with session_factory() as session:
		dados = UsuarioCadastroEntrada(
			nome="Carlos Souza",
			email="carlos@example.com",
			senha="senhaforte123",
			perfil="CIDADAO",
		)
		user, token = cadastrar_usuario(session, dados)
		assert user.id is not None
		assert user.email == "carlos@example.com"
		assert user.perfil == "CIDADAO"
		assert len(token) > 20

		payload = decodificar_token_jwt(token)
		assert payload["sub"] == str(user.id)


def test_cadastro_usuario_rejeita_email_duplicado() -> None:
	session_factory = _setup_test_db()
	with session_factory() as session:
		dados = UsuarioCadastroEntrada(
			nome="Carlos Souza",
			email="carlos@example.com",
			senha="senhaforte123",
			perfil="CIDADAO",
		)
		cadastrar_usuario(session, dados)

		import pytest

		with pytest.raises(EmailJaCadastradoError):
			cadastrar_usuario(session, dados)


def test_autenticacao_service_sucesso_e_falha() -> None:
	session_factory = _setup_test_db()
	with session_factory() as session:
		dados = UsuarioCadastroEntrada(
			nome="Empresa XPTO",
			email="contato@xpto.com",
			senha="senha_correta_123",
			perfil="EMPRESA",
		)
		cadastrar_usuario(session, dados)

		import pytest

		# Sucesso
		login_dados = UsuarioLoginEntrada(email="contato@xpto.com", senha="senha_correta_123")
		user, token = autenticar_usuario(session, login_dados)
		assert user.nome == "Empresa XPTO"
		assert len(token) > 10

		# Senha errada
		login_dados_errado = UsuarioLoginEntrada(email="contato@xpto.com", senha="senha_errada")
		with pytest.raises(CredenciaisInvalidasError):
			autenticar_usuario(session, login_dados_errado)

		# Email inexistente
		login_dados_inexistente = UsuarioLoginEntrada(email="naoexiste@xpto.com", senha="123")
		with pytest.raises(CredenciaisInvalidasError):
			autenticar_usuario(session, login_dados_inexistente)


def test_buscar_usuarios_filtro_perfil_e_busca() -> None:
	session_factory = _setup_test_db()
	with session_factory() as session:
		cadastrar_usuario(
			session,
			UsuarioCadastroEntrada(
				nome="Hospital Santa Casa",
				email="admin@santacasa.org",
				senha="senha123456",
				perfil="EMPRESA",
			),
		)
		cadastrar_usuario(
			session,
			UsuarioCadastroEntrada(
				nome="Universidade Nacional",
				email="secretaria@unacional.edu",
				senha="senha123456",
				perfil="INSTITUICAO",
			),
		)
		cadastrar_usuario(
			session,
			UsuarioCadastroEntrada(
				nome="Ana Beatriz",
				email="ana@gmail.com",
				senha="senha123456",
				perfil="CIDADAO",
			),
		)

		empresas = buscar_usuarios(session, perfil="EMPRESA")
		assert len(empresas) == 1
		assert empresas[0].nome == "Hospital Santa Casa"

		resultado_busca = buscar_usuarios(session, busca="Nacional")
		assert len(resultado_busca) == 1
		assert resultado_busca[0].nome == "Universidade Nacional"


def test_auth_rotas_com_client() -> None:
	session_factory = _setup_test_db()

	def override_get_db():
		with session_factory() as session:
			yield session

	app.dependency_overrides[get_db] = override_get_db
	client = TestClient(app)

	try:
		# 1. Register
		reg_resp = client.post(
			"/auth/register",
			json={
				"nome": "João Silva",
				"email": "joao@example.com",
				"senha": "password123",
				"perfil": "CIDADAO",
			},
		)
		assert reg_resp.status_code == 201
		dados = reg_resp.json()
		assert "access_token" in dados
		assert dados["usuario"]["email"] == "joao@example.com"
		token = dados["access_token"]

		# 2. Duplicate Register -> 409
		dup_resp = client.post(
			"/auth/register",
			json={
				"nome": "João Silva",
				"email": "joao@example.com",
				"senha": "password123",
				"perfil": "CIDADAO",
			},
		)
		assert dup_resp.status_code == 409

		# 3. Login
		login_resp = client.post(
			"/auth/login",
			json={"email": "joao@example.com", "senha": "password123"},
		)
		assert login_resp.status_code == 200
		assert login_resp.json()["usuario"]["nome"] == "João Silva"

		# 4. Login Inválido -> 401
		login_fail = client.post(
			"/auth/login",
			json={"email": "joao@example.com", "senha": "senha_errada_123"},
		)
		assert login_fail.status_code == 401

		# 5. /auth/me sem token -> 401
		me_fail = client.get("/auth/me")
		assert me_fail.status_code == 401

		# 6. /auth/me com token -> 200
		me_ok = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
		assert me_ok.status_code == 200
		assert me_ok.json()["email"] == "joao@example.com"

		# 7. /auth/users com token -> 200
		users_resp = client.get("/auth/users", headers={"Authorization": f"Bearer {token}"})
		assert users_resp.status_code == 200
		assert len(users_resp.json()) == 1
	finally:
		app.dependency_overrides.clear()
