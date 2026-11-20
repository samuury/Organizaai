"""Testes de expiração, revogação e consulta de consentimentos."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.modules.consent.models import DocumentConsent
from app.modules.consent.service import (
	consulta_documento_compartilhado,
	consentimento_ativo,
	conceder_acesso,
	revogar_acesso,
)


def _consentimento(*, expiracao: datetime, revogado_em: datetime | None = None) -> DocumentConsent:
	return DocumentConsent(
		id=1,
		documento_id=20,
		cidadao_id=5,
		empresa_id=11,
		expira_em=expiracao,
		revogado_em=revogado_em,
	)


def test_consentimento_ativo_antes_da_expiracao() -> None:
	now = datetime(2026, 11, 20, tzinfo=timezone.utc)
	consent = _consentimento(expiracao=now + timedelta(seconds=1))

	assert consentimento_ativo(consent, agora=now)


def test_consentimento_expirado_nao_concede_acesso() -> None:
	now = datetime(2026, 11, 20, tzinfo=timezone.utc)
	consent = _consentimento(expiracao=now)

	assert not consentimento_ativo(consent, agora=now)


def test_consentimento_revogado_nao_concede_acesso() -> None:
	now = datetime(2026, 11, 20, tzinfo=timezone.utc)
	consent = _consentimento(
		expiracao=now + timedelta(days=1),
		revogado_em=now - timedelta(seconds=1),
	)

	assert not consentimento_ativo(consent, agora=now)


def test_conceder_acesso_rejeita_expiracao_passada() -> None:
	session = Mock(spec=Session)

	with pytest.raises(ValueError, match="futuro"):
		conceder_acesso(
			session,
			cidadao_id=5,
			documento_id=20,
			empresa_id=11,
			expira_em=datetime.now(timezone.utc) - timedelta(seconds=1),
		)

	session.scalar.assert_not_called()


def test_revogacao_define_timestamp_e_persiste_auditoria() -> None:
	session = Mock(spec=Session)
	consent = _consentimento(expiracao=datetime.now(timezone.utc) + timedelta(days=1))
	session.scalar.return_value = consent

	result = revogar_acesso(session, cidadao_id=5, consentimento_id=1)

	assert result.revogado_em is not None
	assert result.revogado_em.tzinfo == timezone.utc
	session.commit.assert_called_once()
	session.add.assert_called_once()


def test_consulta_de_conteudo_exige_empresa_consenso_ativo() -> None:
	statement = consulta_documento_compartilhado(empresa_id=11, documento_id=20)
	compiled = str(statement.compile(dialect=postgresql.dialect()))

	assert "document_consents.empresa_id" in compiled
	assert "document_consents.revogado_em IS NULL" in compiled
	assert "document_consents.expira_em > now()" in compiled