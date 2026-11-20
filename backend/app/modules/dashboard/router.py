"""Rotas de indicadores do dashboard."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.dashboard.schemas import DashboardResumoResposta
from app.modules.dashboard.service import obter_resumo

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/resumo", response_model=DashboardResumoResposta)
def resumo(
	request: Request,
	session: Annotated[Session, Depends(get_db)],
) -> DashboardResumoResposta:
	"""Retorna indicadores agregados sem dados pessoais."""
	user_id = getattr(request.state, "user_id", None)
	if not isinstance(user_id, int) or user_id < 1:
		raise HTTPException(status_code=401, detail="Autenticação obrigatória.")
	return obter_resumo(session)