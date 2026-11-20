"""Testes de resposta pública, auditoria e rate limit da verificação."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from app.core.database import get_db
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.issuance.models import IssuanceBatch, IssuedDocument


def test_verification_limits_ip_audits_and_minimizes_public_data() -> None:
	engine = create_engine(
		"sqlite://",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	IssuanceBatch.__table__.create(engine)
	IssuedDocument.__table__.create(engine)
	AuditLog.__table__.create(engine)
	test_session_factory = sessionmaker(bind=engine, expire_on_commit=False)
	valid_code = "a" * 32
	revoked_code = "b" * 32
	with test_session_factory() as session:
		session.add_all(
			[
				IssuedDocument(
					instituicao_id=9,
					emissor="Universidade Federal",
					usuario_id=73,
					titulo="Dados pessoais não públicos",
					tipo_documento="diploma",
					conteudo={"nome": "Pessoa titular"},
					codigo=valid_code,
					hash_sha256="c" * 64,
					qr_code_png=b"png",
					estado="emitido",
					emitido_em=datetime(2026, 1, 2, tzinfo=timezone.utc),
				),
				IssuedDocument(
					instituicao_id=9,
					emissor="Cartório Central",
					usuario_id=74,
					titulo="Certidão",
					tipo_documento="certidao",
					conteudo={"nome": "Outra pessoa"},
					codigo=revoked_code,
					hash_sha256="d" * 64,
					qr_code_png=b"png",
					estado="revogado",
					emitido_em=datetime(2025, 6, 7, tzinfo=timezone.utc),
				),
			]
		)
		session.commit()

	def override_get_db():
		with test_session_factory() as session:
			yield session

	app.dependency_overrides[get_db] = override_get_db
	original_audit_session_factory = app.state.audit_session_factory
	app.state.audit_session_factory = test_session_factory
	try:
		with TestClient(app, client=("198.51.100.40", 1234)) as client:
			first_response = client.get(f"/verificar/{valid_code}")
			assert first_response.status_code == 200
			assert first_response.json() == {
				"status": "VALIDO",
				"emissor": "Universidade Federal",
				"data_emissao": "2026-01-02T00:00:00",
			}
			for _ in range(59):
				assert client.get(f"/verificar/{valid_code}").status_code == 200
			assert client.get(f"/verificar/{valid_code}").status_code == 429

		with TestClient(app, client=("198.51.100.41", 1234)) as client:
			invalid_response = client.get("/verificar/codigo-inexistente")
			assert invalid_response.status_code == 200
			assert invalid_response.json() == {
				"status": "INVALIDO",
				"emissor": None,
				"data_emissao": None,
			}
			revoked_response = client.get(f"/verificar/{revoked_code}")
			assert revoked_response.json() == {
				"status": "REVOGADO",
				"emissor": "Cartório Central",
				"data_emissao": "2025-06-07T00:00:00",
			}

		with test_session_factory() as session:
			audit_count = session.scalar(select(func.count()).select_from(AuditLog))
		assert audit_count == 63
	finally:
		app.dependency_overrides.pop(get_db, None)
		app.state.audit_session_factory = original_audit_session_factory
		engine.dispose()