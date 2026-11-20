"""Modelo de documento armazenado na carteira."""

from datetime import date, datetime

from sqlalchemy import (
	CheckConstraint,
	Computed,
	Date,
	DateTime,
	Index,
	Integer,
	String,
	Text,
	func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

_SEARCH_VECTOR_EXPRESSION = """
setweight(to_tsvector('portuguese', coalesce(nome_arquivo, '')), 'D') ||
setweight(to_tsvector('portuguese', coalesce(tipo_documento, '')), 'A') ||
setweight(to_tsvector('portuguese', coalesce(nome_extraido, '')), 'A') ||
setweight(to_tsvector('portuguese', coalesce(emissor_extraido, '')), 'B') ||
setweight(to_tsvector('simple', coalesce(extract(year from data_extraida)::text, '')), 'B') ||
setweight(to_tsvector('portuguese', coalesce(texto_ocr, '')), 'C')
"""


class WalletDocument(Base):
	"""Documento enviado por um usuário da carteira."""

	__tablename__ = "wallet_documents"
	__table_args__ = (
		CheckConstraint(
			"tamanho_bytes > 0 AND tamanho_bytes <= 10485760",
			name="ck_wallet_documents_tamanho",
		),
		CheckConstraint(
			"tipo_documento IS NULL OR tipo_documento IN "
			"('diploma', 'certidao', 'comprovante')",
			name="ck_wallet_documents_tipo",
		),
		CheckConstraint(
			"estado_processamento IN ('pendente', 'processando', 'concluido', 'falhou')",
			name="ck_wallet_documents_estado",
		),
		Index("ix_wallet_documents_usuario_criado", "usuario_id", "criado_em"),
		Index("ix_wallet_documents_search_vector", "search_vector", postgresql_using="gin"),
	)

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	usuario_id: Mapped[int] = mapped_column(Integer, nullable=False)
	nome_arquivo: Mapped[str] = mapped_column(String(255), nullable=False)
	storage_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
	content_type: Mapped[str] = mapped_column(String(100), nullable=False)
	tamanho_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
	estado_processamento: Mapped[str] = mapped_column(
		String(20), nullable=False, default="pendente", server_default="pendente"
	)
	tipo_documento: Mapped[str | None] = mapped_column(String(20), nullable=True)
	nome_extraido: Mapped[str | None] = mapped_column(String(255), nullable=True)
	data_extraida: Mapped[date | None] = mapped_column(Date, nullable=True)
	emissor_extraido: Mapped[str | None] = mapped_column(String(255), nullable=True)
	texto_ocr: Mapped[str | None] = mapped_column(Text, nullable=True)
	erro_processamento: Mapped[str | None] = mapped_column(String(255), nullable=True)
	criado_em: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), nullable=False, server_default=func.now()
	)
	atualizado_em: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		nullable=False,
		server_default=func.now(),
		onupdate=func.now(),
	)
	search_vector: Mapped[str] = mapped_column(
		TSVECTOR,
		Computed(_SEARCH_VECTOR_EXPRESSION, persisted=True),
		nullable=False,
	)