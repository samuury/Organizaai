"""Modelos de documentos emitidos e lotes de emissão."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
	CheckConstraint,
	DateTime,
	ForeignKey,
	Index,
	Integer,
	JSON,
	LargeBinary,
	String,
	Text,
	func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IssuanceBatch(Base):
	"""Estado e relatórios de um lote de emissão."""

	__tablename__ = "issuance_batches"
	__table_args__ = (
		CheckConstraint(
			"estado IN ('pendente', 'processando', 'concluido', 'concluido_com_erros')",
			name="ck_issuance_batches_estado",
		),
		Index("ix_issuance_batches_instituicao_criado", "instituicao_id", "criado_em"),
	)

	id: Mapped[str] = mapped_column(String(32), primary_key=True)
	instituicao_id: Mapped[int] = mapped_column(Integer, nullable=False)
	emissor: Mapped[str] = mapped_column(String(255), nullable=False, server_default="Instituição")
	estado: Mapped[str] = mapped_column(
		String(24), nullable=False, default="pendente", server_default="pendente"
	)
	total_linhas: Mapped[int] = mapped_column(Integer, nullable=False)
	validas: Mapped[int] = mapped_column(Integer, nullable=False)
	erros_validacao: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
	erros_processamento: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
	criado_em: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), nullable=False, server_default=func.now()
	)
	finalizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IssuedDocument(Base):
	"""Documento emitido por uma instituição para um usuário."""

	__tablename__ = "issued_documents"
	__table_args__ = (
		CheckConstraint(
			"tipo_documento IN ('diploma', 'certidao', 'comprovante')",
			name="ck_issued_documents_tipo",
		),
		CheckConstraint(
			"estado IN ('emitido', 'revogado')",
			name="ck_issued_documents_estado",
		),
		CheckConstraint("length(hash_sha256) = 64", name="ck_issued_documents_hash"),
		Index("ix_issued_documents_instituicao", "instituicao_id"),
		Index("ix_issued_documents_usuario", "usuario_id"),
		Index("ix_issued_documents_lote_linha", "lote_id", "linha_lote"),
		Index("ix_issued_documents_emitido_em", "emitido_em"),
	)

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	instituicao_id: Mapped[int] = mapped_column(Integer, nullable=False)
	emissor: Mapped[str] = mapped_column(String(255), nullable=False, server_default="Instituição")
	usuario_id: Mapped[int] = mapped_column(Integer, nullable=False)
	lote_id: Mapped[str | None] = mapped_column(
		ForeignKey("issuance_batches.id", ondelete="SET NULL"), nullable=True
	)
	linha_lote: Mapped[int | None] = mapped_column(Integer, nullable=True)
	titulo: Mapped[str] = mapped_column(String(255), nullable=False)
	tipo_documento: Mapped[str] = mapped_column(String(20), nullable=False)
	conteudo: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
	codigo: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
	hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
	qr_code_png: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
	estado: Mapped[str] = mapped_column(
		String(12), nullable=False, default="emitido", server_default="emitido"
	)
	motivo_revogacao: Mapped[str | None] = mapped_column(Text, nullable=True)
	emitido_em: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), nullable=False, server_default=func.now()
	)
	revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)