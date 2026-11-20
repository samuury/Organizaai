"""Testes do chatbot assistente com Anthropic Claude Haiku."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.auth.models import User
from app.modules.auth.service import cadastrar_usuario
from app.modules.auth.schemas import UsuarioCadastroEntrada
from app.modules.chat.schemas import MensagemChat
from app.modules.chat.service import processar_mensagem_chat


@pytest.mark.anyio
async def test_servico_chat_fallback_inteligente() -> None:
	resposta_consent, modelo = await processar_mensagem_chat(
		mensagem="Como funciona o consentimento para empresas?",
		historico=[],
		usuario_nome="Roberta",
		usuario_perfil="CIDADAO",
	)
	assert "Roberta" in resposta_consent
	assert "consentimento" in resposta_consent.lower() or "lgpd" in resposta_consent.lower()
	assert "haiku" in modelo.lower()

	resposta_emissao, _ = await processar_mensagem_chat(
		mensagem="Como emitir um documento com QR Code?",
		historico=[],
	)
	assert "qr code" in resposta_emissao.lower() or "lote" in resposta_emissao.lower()


def test_endpoint_chat_message() -> None:
	engine = create_engine(
		"sqlite://",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	AuditLog.__table__.create(engine)
	User.__table__.create(engine)
	session_factory = sessionmaker(bind=engine, expire_on_commit=False)

	def override_get_db():
		with session_factory() as session:
			yield session

	app.dependency_overrides[get_db] = override_get_db
	client = TestClient(app)

	try:
		with session_factory() as session:
			user, token = cadastrar_usuario(
				session,
				UsuarioCadastroEntrada(
					nome="Gabriel Santos",
					email="gabriel@example.com",
					senha="senha_forte_123",
					perfil="CIDADAO",
				),
			)

		response = client.post(
			"/chat/message",
			json={
				"mensagem": "Como posso verificar um certificado emitido?",
				"historico": [
					{"role": "user", "content": "Olá"},
					{"role": "assistant", "content": "Olá! Como posso ajudar?"},
				],
			},
			headers={"Authorization": f"Bearer {token}"},
		)

		assert response.status_code == 200
		dados = response.json()
		assert "resposta" in dados
		assert "modelo" in dados
		assert "Gabriel" in dados["resposta"]
		assert "haiku" in dados["modelo"].lower()
	finally:
		app.dependency_overrides.clear()
