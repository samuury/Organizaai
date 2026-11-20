"""Testes de agregação do resumo do dashboard."""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.modules.audit.models import AuditLog
from app.modules.dashboard.service import PERIODO_DIAS, obter_resumo
from app.modules.issuance.models import IssuanceBatch, IssuedDocument


def test_resumo_agrega_documentos_verificacoes_e_usuarios_ativos() -> None:
	engine = create_engine(
		"sqlite://",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	IssuanceBatch.__table__.create(engine)
	IssuedDocument.__table__.create(engine)
	AuditLog.__table__.create(engine)
	today = date(2026, 11, 20)
	emitted_at = datetime.combine(today, time(10), tzinfo=timezone.utc)
	with Session(engine) as session:
		session.add(
			IssuedDocument(
				instituicao_id=9,
				emissor="Instituição de teste",
				usuario_id=73,
				titulo="Diploma",
				tipo_documento="diploma",
				conteudo={"ano": 2023},
				codigo="a" * 32,
				hash_sha256="b" * 64,
				qr_code_png=b"png",
				estado="emitido",
				emitido_em=emitted_at,
			)
		)
		session.add_all(
			[
				AuditLog(
					usuario_id=73,
					acao="verification.codigo_valido",
					entidade="issued_documents",
					entidade_id="1",
					criado_em=emitted_at,
				),
				AuditLog(
					usuario_id=84,
					acao="verification.codigo_revogado",
					entidade="issued_documents",
					entidade_id="2",
					criado_em=emitted_at,
				),
				AuditLog(
					usuario_id=73,
					acao="consent.acesso_concedido",
					entidade="document_consents",
					criado_em=emitted_at,
				),
			]
		)
		session.commit()

		result = obter_resumo(session, hoje=today)

	assert result.documentos_emitidos == 1
	assert result.verificacoes == 2
	assert result.usuarios_ativos == 2
	assert result.periodo_dias == PERIODO_DIAS
	assert len(result.tendencia) == PERIODO_DIAS
	assert result.tendencia[-1].data == today
	assert result.tendencia[-1].documentos_emitidos == 1
	assert result.tendencia[-1].verificacoes == 2
	engine.dispose()