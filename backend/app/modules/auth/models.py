"""Modelos de autenticação e usuários."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
	"""Usuário cadastrado na plataforma Organiza AI."""

	__tablename__ = "users"
	__table_args__ = (
		CheckConstraint(
			"perfil IN ('CIDADAO', 'INSTITUICAO', 'EMPRESA')",
			name="ck_users_perfil",
		),
	)

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	nome: Mapped[str] = mapped_column(String(255), nullable=False)
	email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
	senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
	perfil: Mapped[str] = mapped_column(String(20), nullable=False)
	criado_em: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), nullable=False, server_default=func.now()
	)
	atualizado_em: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		nullable=False,
		server_default=func.now(),
		onupdate=func.now(),
	)
