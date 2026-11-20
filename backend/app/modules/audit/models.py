"""Modelo de auditoria imutável."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
	"""Registro de uma ação realizada no sistema."""

	__tablename__ = "audit_log"
	__table_args__ = (
		Index("ix_audit_log_acao_criado", "acao", "criado_em"),
		Index("ix_audit_log_criado_usuario", "criado_em", "usuario_id"),
	)

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
	acao: Mapped[str] = mapped_column(String(100), nullable=False)
	entidade: Mapped[str] = mapped_column(String(100), nullable=False)
	entidade_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
	dados_antes: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON, nullable=True)
	dados_depois: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON, nullable=True)
	ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
	criado_em: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), nullable=False, server_default=func.now()
	)