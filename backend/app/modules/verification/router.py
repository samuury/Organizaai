"""Verificação pública de autenticidade por código."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.notifications import notificar_tentativas_suspeitas
from app.core.rate_limit import limiter
from app.modules.audit.service import registrar_auditoria
from app.modules.issuance.models import IssuedDocument
from app.modules.issuance.schemas import VerificacaoPublicaResposta

router = APIRouter(tags=["verification"])


def _status_documento(estado: str | None) -> str:
	if estado == "emitido":
		return "VALIDO"
	if estado == "revogado":
		return "REVOGADO"
	return "INVALIDO"


@router.get("/verificar/{codigo}", response_model=VerificacaoPublicaResposta)
@limiter.limit("60/minute")
def verificar_documento(
	codigo: str,
	request: Request,
	background_tasks: BackgroundTasks,
	session: Annotated[Session, Depends(get_db)],
):
	"""Retorna estado, emissor e data sem carregar ou revelar dados do titular."""
	accept_header = request.headers.get("accept", "")
	if "text/html" in accept_header and settings.frontend_origin:
		frontend_url = f"{settings.frontend_origin.rstrip('/')}/verificar/{codigo}"
		return RedirectResponse(url=frontend_url, status_code=307)

	row = session.execute(
		select(
			IssuedDocument.id,
			IssuedDocument.estado,
			IssuedDocument.emissor,
			IssuedDocument.emitido_em,
		).where(IssuedDocument.codigo == codigo)
	).one_or_none()
	status = _status_documento(row.estado if row else None)
	registrar_auditoria(
		session,
		usuario_id=None,
		acao=f"verification.codigo_{status.lower()}",
		entidade="issued_documents",
		entidade_id=row.id if row else codigo,
		dados_depois={"status": status},
		ip=request.client.host if request.client else None,
	)
	session.commit()
	if status == "INVALIDO":
		background_tasks.add_task(
			notificar_tentativas_suspeitas,
			request.client.host if request.client else None,
			request.app.state.audit_session_factory,
		)
	return VerificacaoPublicaResposta(
		status=status,
		emissor=row.emissor if row else None,
		data_emissao=row.emitido_em if row else None,
	)