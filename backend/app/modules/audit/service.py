"""Operações de auditoria."""

from typing import Any

from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog


def registrar_auditoria(
	session: Session,
	*,
	acao: str,
	entidade: str,
	usuario_id: int | None = None,
	entidade_id: int | str | None = None,
	dados_antes: dict[str, Any] | list[Any] | None = None,
	dados_depois: dict[str, Any] | list[Any] | None = None,
	ip: str | None = None,
) -> AuditLog:
	"""Adiciona um evento de auditoria à transação atual."""
	registro = AuditLog(
		usuario_id=usuario_id,
		acao=acao,
		entidade=entidade,
		entidade_id=str(entidade_id) if entidade_id is not None else None,
		dados_antes=dados_antes,
		dados_depois=dados_depois,
		ip=ip,
	)
	session.add(registro)
	return registro