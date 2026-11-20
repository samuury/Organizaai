"""Testes ponta a ponta dos fluxos autenticados de emissão, verificação e consentimento."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.auth.models import User
from app.modules.consent.models import DocumentConsent
from app.modules.issuance.models import IssuanceBatch, IssuedDocument
from app.modules.wallet.models import WalletDocument
from app.modules.wallet.router import get_storage_service
from app.modules.wallet.storage import StorageService


class MemoryStorage(StorageService):
	def __init__(self):
		self.files: dict[str, bytes] = {}

	def save(self, key: str, content: bytes) -> None:
		self.files[key] = content

	def read(self, key: str) -> bytes:
		if key not in self.files:
			raise FileNotFoundError()
		return self.files[key]

	def delete(self, key: str) -> None:
		self.files.pop(key, None)


def _setup_all_tables():
	engine = create_engine(
		"sqlite://",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	AuditLog.__table__.create(engine)
	User.__table__.create(engine)
	IssuanceBatch.__table__.create(engine)
	IssuedDocument.__table__.create(engine)
	return engine, sessionmaker(bind=engine, expire_on_commit=False)


def test_fluxo_completo_emissao_verificacao_e_revogacao() -> None:
	engine, session_factory = _setup_all_tables()
	storage = MemoryStorage()

	def override_get_db():
		with session_factory() as session:
			yield session

	app.dependency_overrides[get_db] = override_get_db
	app.dependency_overrides[get_storage_service] = lambda: storage
	app.state.audit_session_factory = session_factory
	client = TestClient(app)

	try:
		# 1. Cadastra Instituição e Cidadão
		resp_inst = client.post(
			"/auth/register",
			json={
				"nome": "Universidade Estadual",
				"email": "reitoria@ue.edu.br",
				"senha": "senha_instituicao",
				"perfil": "INSTITUICAO",
			},
		)
		assert resp_inst.status_code == 201
		token_inst = resp_inst.json()["access_token"]
		inst_id = resp_inst.json()["usuario"]["id"]

		resp_cid = client.post(
			"/auth/register",
			json={
				"nome": "Lucas Ferreira",
				"email": "lucas@cidadao.com",
				"senha": "senha_cidadao_123",
				"perfil": "CIDADAO",
			},
		)
		assert resp_cid.status_code == 201
		token_cid = resp_cid.json()["access_token"]
		cid_id = resp_cid.json()["usuario"]["id"]

		# 2. Instituição busca usuários cadastrados para selecionar titular
		users_resp = client.get(
			"/auth/users?perfil=CIDADAO",
			headers={"Authorization": f"Bearer {token_inst}"},
		)
		assert users_resp.status_code == 200
		cidadaos = users_resp.json()
		assert any(c["id"] == cid_id for c in cidadaos)

		# 3. Tentativa de emissão por cidadão é negada (403 Forbidden)
		resp_proibida = client.post(
			"/issuance",
			json={
				"usuario_id": cid_id,
				"titulo": "Diploma de Computação",
				"tipo_documento": "diploma",
				"conteudo": {"curso": "Ciência da Computação", "ano": 2024},
			},
			headers={"Authorization": f"Bearer {token_cid}"},
		)
		assert resp_proibida.status_code == 403

		# 4. Emissão legítima pela Instituição
		resp_emissao = client.post(
			"/issuance",
			json={
				"usuario_id": cid_id,
				"titulo": "Diploma de Computação",
				"tipo_documento": "diploma",
				"conteudo": {"curso": "Ciência da Computação", "ano": 2024},
			},
			headers={"Authorization": f"Bearer {token_inst}"},
		)
		assert resp_emissao.status_code == 201
		doc_emitido = resp_emissao.json()
		codigo = doc_emitido["codigo"]
		assert len(codigo) == 32
		assert doc_emitido["estado"] == "emitido"

		# 5. Consulta do QR code pela instituição
		qr_resp = client.get(
			f"/issuance/{codigo}/qr",
			headers={"Authorization": f"Bearer {token_inst}"},
		)
		assert qr_resp.status_code == 200
		assert qr_resp.headers["content-type"] == "image/png"

		# 6. Verificação pública anônima do documento emitido
		verif_resp = client.get(f"/verificar/{codigo}")
		assert verif_resp.status_code == 200
		verif_data = verif_resp.json()
		assert verif_data["status"] == "VALIDO"
		assert verif_data["emissor"] == "Universidade Estadual"

		# 7. Instituição revoga o documento
		revoga_resp = client.post(
			f"/issuance/{codigo}/revoke",
			json={"motivo": "Cancelamento de matrícula por duplicidade"},
			headers={"Authorization": f"Bearer {token_inst}"},
		)
		assert revoga_resp.status_code == 200
		assert revoga_resp.json()["estado"] == "revogado"

		# 8. Verificação pública anônima agora reporta REVOGADO
		verif_revogado = client.get(f"/verificar/{codigo}")
		assert verif_revogado.status_code == 200
		assert verif_revogado.json()["status"] == "REVOGADO"

	finally:
		app.dependency_overrides.clear()


def test_fluxo_lote_com_instituicao() -> None:
	engine, session_factory = _setup_all_tables()

	def override_get_db():
		with session_factory() as session:
			yield session

	app.dependency_overrides[get_db] = override_get_db
	app.state.audit_session_factory = session_factory
	client = TestClient(app)

	try:
		# Cadastra instituição
		resp_inst = client.post(
			"/auth/register",
			json={
				"nome": "Faculdade Central",
				"email": "coord@fcentral.edu.br",
				"senha": "senha_instituicao",
				"perfil": "INSTITUICAO",
			},
		)
		token_inst = resp_inst.json()["access_token"]

		# Envia lote JSON
		json_content = (
			'[{"usuario_id": 10, "titulo": "Certificado de Extensao", "tipo_documento": "certidao", "conteudo": {"curso": "Python", "ano": 2024}},'
			' {"usuario_id": 11, "titulo": "Diploma de Especializacao", "tipo_documento": "diploma", "conteudo": {"curso": "IA", "ano": 2023}}]'
		).encode("utf-8")

		batch_resp = client.post(
			"/issuance/batch",
			files={"file": ("lote_teste.json", json_content, "application/json")},
			headers={"Authorization": f"Bearer {token_inst}"},
		)
		assert batch_resp.status_code == 202
		batch_id = batch_resp.json()["lote_id"]
		assert batch_resp.json()["total_linhas"] == 2
		assert batch_resp.json()["validas"] == 2

		# Consulta lote
		consulta_resp = client.get(
			f"/issuance/batch/{batch_id}",
			headers={"Authorization": f"Bearer {token_inst}"},
		)
		assert consulta_resp.status_code == 200
		assert consulta_resp.json()["total_linhas"] == 2

	finally:
		app.dependency_overrides.clear()


def test_fluxo_consentimento_cidadao_empresa() -> None:
	engine, session_factory = _setup_all_tables()
	# Cria tabela document_consents manualmente para o teste com mock de wallet_documents
	with engine.connect() as conn:
		conn.exec_driver_sql(
			"""
			CREATE TABLE wallet_documents (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				usuario_id INTEGER NOT NULL,
				nome_arquivo VARCHAR(255) NOT NULL,
				storage_key VARCHAR(64) NOT NULL,
				content_type VARCHAR(100) NOT NULL,
				tamanho_bytes INTEGER NOT NULL,
				estado_processamento VARCHAR(20) DEFAULT 'pendente',
				tipo_documento VARCHAR(20),
				nome_extraido VARCHAR(255),
				data_extraida DATE,
				emissor_extraido VARCHAR(255),
				texto_ocr TEXT,
				erro_processamento VARCHAR(255),
				criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				search_vector VARCHAR
			)
			"""
		)
		conn.commit()
	DocumentConsent.__table__.create(engine)

	storage = MemoryStorage()

	def override_get_db():
		with session_factory() as session:
			yield session

	app.dependency_overrides[get_db] = override_get_db
	app.dependency_overrides[get_storage_service] = lambda: storage
	app.state.audit_session_factory = session_factory
	client = TestClient(app)

	try:
		# 1. Cadastra cidadão e empresa
		resp_cid = client.post(
			"/auth/register",
			json={
				"nome": "Mariana Ramos",
				"email": "mariana@gmail.com",
				"senha": "senha_segura_123",
				"perfil": "CIDADAO",
			},
		)
		token_cid = resp_cid.json()["access_token"]
		cid_id = resp_cid.json()["usuario"]["id"]

		resp_emp = client.post(
			"/auth/register",
			json={
				"nome": "Tech Corp RH",
				"email": "rh@techcorp.com",
				"senha": "senha_segura_123",
				"perfil": "EMPRESA",
			},
		)
		token_emp = resp_emp.json()["access_token"]
		emp_id = resp_emp.json()["usuario"]["id"]

		# 2. Insere documento do cidadão diretamente
		with session_factory() as session:
			doc = WalletDocument(
				usuario_id=cid_id,
				nome_arquivo="diploma_mariana.pdf",
				storage_key="doc_mariana_key_123",
				content_type="application/pdf",
				tamanho_bytes=1024,
				estado_processamento="concluido",
				tipo_documento="diploma",
				texto_ocr="Diploma de Bacharel em Sistemas de Informação",
			)
			session.add(doc)
			session.commit()
			doc_id = doc.id
			storage.save("doc_mariana_key_123", b"%PDF-mock-diploma")

		# 3. Cidadão concede acesso temporário para a Empresa
		expiracao = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
		consent_resp = client.post(
			"/consent",
			json={
				"documento_id": doc_id,
				"empresa_id": emp_id,
				"expira_em": expiracao,
			},
			headers={"Authorization": f"Bearer {token_cid}"},
		)
		assert consent_resp.status_code == 201
		consent_id = consent_resp.json()["id"]

		# 4. Empresa consulta o conteúdo do documento compartilhado
		conteudo_resp = client.get(
			f"/consent/documents/{doc_id}/content",
			headers={"Authorization": f"Bearer {token_emp}"},
		)
		assert conteudo_resp.status_code == 200
		assert "Sistemas de Informação" in conteudo_resp.json()["conteudo_ocr"]

		# 5. Empresa faz download do documento
		download_resp = client.get(
			f"/consent/documents/{doc_id}/download",
			headers={"Authorization": f"Bearer {token_emp}"},
		)
		assert download_resp.status_code == 200
		assert download_resp.content == b"%PDF-mock-diploma"

		# 6. Cidadão revoga o consentimento
		revog_resp = client.delete(
			f"/consent/{consent_id}",
			headers={"Authorization": f"Bearer {token_cid}"},
		)
		assert revog_resp.status_code == 204

		# 7. Empresa tenta consultar novamente após revogação -> 404
		conteudo_pos_revog = client.get(
			f"/consent/documents/{doc_id}/content",
			headers={"Authorization": f"Bearer {token_emp}"},
		)
		assert conteudo_pos_revog.status_code == 404

	finally:
		app.dependency_overrides.clear()
