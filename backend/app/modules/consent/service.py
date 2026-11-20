"""Concessão, expiração, revogação e validação de acesso consentido."""

from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.modules.audit.service import registrar_auditoria
from app.modules.consent.models import DocumentConsent
from app.modules.issuance.models import IssuedDocument
from app.modules.wallet.models import WalletDocument


def consentimento_ativo(
	consent: DocumentConsent, *, agora: datetime | None = None
) -> bool:
	"""Retorna se a concessão ainda não foi revogada ou expirada."""
	current_time = agora or datetime.now(timezone.utc)
	expiration = consent.expira_em
	if expiration.tzinfo is None:
		expiration = expiration.replace(tzinfo=timezone.utc)
	if current_time.tzinfo is None:
		current_time = current_time.replace(tzinfo=timezone.utc)
	return consent.revogado_em is None and expiration > current_time


def conceder_acesso(
	session: Session,
	*,
	cidadao_id: int,
	documento_id: int,
	empresa_id: int,
	expira_em: datetime,
	ip: str | None = None,
) -> DocumentConsent:
	"""Concede acesso temporário após confirmar a titularidade do documento."""
	now = datetime.now(timezone.utc)
	if expira_em.tzinfo is None:
		expira_em = expira_em.replace(tzinfo=timezone.utc)
	if expira_em <= now:
		raise ValueError("A expiração deve estar no futuro.")

	document_owner = session.scalar(
		select(WalletDocument.usuario_id).where(
			WalletDocument.id == documento_id,
			WalletDocument.usuario_id == cidadao_id,
		)
	)
	if document_owner is None:
		raise LookupError("Documento não encontrado.")

	active_consent = session.scalar(
		select(DocumentConsent.id).where(
			DocumentConsent.documento_id == documento_id,
			DocumentConsent.cidadao_id == cidadao_id,
			DocumentConsent.empresa_id == empresa_id,
			DocumentConsent.revogado_em.is_(None),
			DocumentConsent.expira_em > func.now(),
		)
	)
	if active_consent is not None:
		raise ValueError("Já existe um consentimento ativo para esta empresa e documento.")

	consent = DocumentConsent(
		documento_id=documento_id,
		cidadao_id=cidadao_id,
		empresa_id=empresa_id,
		expira_em=expira_em,
	)
	session.add(consent)
	session.flush()
	registrar_auditoria(
		session,
		usuario_id=cidadao_id,
		acao="consent.acesso_concedido",
		entidade="document_consents",
		entidade_id=consent.id,
		dados_depois={
			"documento_id": documento_id,
			"empresa_id": empresa_id,
			"expira_em": expira_em.isoformat(),
		},
		ip=ip,
	)
	session.commit()
	session.refresh(consent)
	return consent


def revogar_acesso(
	session: Session,
	*,
	cidadao_id: int,
	consentimento_id: int,
	ip: str | None = None,
) -> DocumentConsent:
	"""Revoga uma concessão pertencente ao titular autenticado."""
	consent = session.scalar(
		select(DocumentConsent).where(
			DocumentConsent.id == consentimento_id,
			DocumentConsent.cidadao_id == cidadao_id,
		)
	)
	if consent is None:
		raise LookupError("Consentimento não encontrado.")
	if consent.revogado_em is not None:
		raise ValueError("O consentimento já foi revogado.")

	consent.revogado_em = datetime.now(timezone.utc)
	registrar_auditoria(
		session,
		usuario_id=cidadao_id,
		acao="consent.acesso_revogado",
		entidade="document_consents",
		entidade_id=consent.id,
		dados_antes={"ativo": True},
		dados_depois={"ativo": False},
		ip=ip,
	)
	session.commit()
	session.refresh(consent)
	return consent


def listar_acessos_ativos(
	session: Session,
	*,
	cidadao_id: int,
	ip: str | None = None,
) -> list[DocumentConsent]:
	"""Lista somente as concessões ainda válidas do titular."""
	consents = list(
		session.scalars(
			select(DocumentConsent)
			.where(
				DocumentConsent.cidadao_id == cidadao_id,
				DocumentConsent.revogado_em.is_(None),
				DocumentConsent.expira_em > func.now(),
			)
			.order_by(DocumentConsent.expira_em)
		).all()
	)
	registrar_auditoria(
		session,
		usuario_id=cidadao_id,
		acao="consent.acessos_listados",
		entidade="document_consents",
		ip=ip,
	)
	session.commit()
	return consents


def consulta_documento_compartilhado(
	empresa_id: int, documento_id: int
) -> Select[tuple[WalletDocument, DocumentConsent]]:
	"""Monta a consulta que exige consentimento não revogado e não expirado."""
	consent_join = and_(
		DocumentConsent.documento_id == WalletDocument.id,
		DocumentConsent.cidadao_id == WalletDocument.usuario_id,
	)
	return (
		select(WalletDocument, DocumentConsent)
		.join(DocumentConsent, consent_join)
		.where(
			WalletDocument.id == documento_id,
			DocumentConsent.empresa_id == empresa_id,
			DocumentConsent.revogado_em.is_(None),
			DocumentConsent.expira_em > func.now(),
		)
	)


def obter_documento_compartilhado(
	session: Session,
	*,
	empresa_id: int,
	documento_id: int,
	ip: str | None = None,
	acao: str = "consent.documento_consultado",
) -> WalletDocument:
	"""Busca conteúdo somente quando existe concessão ativa para a empresa."""
	row = session.execute(
		consulta_documento_compartilhado(empresa_id, documento_id)
	).one_or_none()
	document = row[0] if row is not None and consentimento_ativo(row[1]) else None
	if document is None:
		registrar_auditoria(
			session,
			usuario_id=empresa_id,
			acao="consent.documento_acesso_negado",
			entidade="wallet_documents",
			entidade_id=documento_id,
			ip=ip,
		)
		session.commit()
		raise LookupError("Documento não encontrado ou sem consentimento ativo.")

	registrar_auditoria(
		session,
		usuario_id=empresa_id,
		acao=acao,
		entidade="wallet_documents",
		entidade_id=document.id,
		ip=ip,
	)
	session.commit()
	return document