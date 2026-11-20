"""Concessões de acesso de empresas a documentos da carteira."""

from datetime import datetime

from sqlalchemy import (
	CheckConstraint,
	DateTime,
	ForeignKey,
	Index,
	Integer,
	func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocumentConsent(Base):
	"""Consentimento de um titular para uma empresa acessar um documento."""

	__tablename__ = "document_consents"
	__table_args__ = (
		CheckConstraint("empresa_id > 0", name="ck_document_consents_empresa_id"),
		Index(
			"ix_document_consents_document_company_expiry",
			"documento_id",
			"empresa_id",
			"expira_em",
		),
		Index("ix_document_consents_owner_expiry", "cidadao_id", "expira_em"),
	)

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	documento_id: Mapped[int] = mapped_column(
		ForeignKey("wallet_documents.id", ondelete="CASCADE"), nullable=False
	)
	cidadao_id: Mapped[int] = mapped_column(Integer, nullable=False)
	empresa_id: Mapped[int] = mapped_column(Integer, nullable=False)
	expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	criado_em: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), nullable=False, server_default=func.now()
	)