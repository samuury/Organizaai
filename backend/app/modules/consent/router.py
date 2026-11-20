"""Rotas de concessão, revogação e uso de acesso consentido."""

import unicodedata
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.notifications import notificar_tentativas_suspeitas
from app.modules.consent.schemas import (
	AcessoAtivoResposta,
	ConsentimentoResposta,
	ConcederAcessoEntrada,
	ConteudoCompartilhadoResposta,
)
from app.modules.consent.service import (
	conceder_acesso,
	listar_acessos_ativos,
	obter_documento_compartilhado,
	revogar_acesso,
)
from app.modules.wallet.router import get_storage_service
from app.modules.wallet.storage import StorageService

router = APIRouter(prefix="/consent", tags=["consent"])


def _identidade(request: Request, papel_esperado: str) -> int:
	user_id = getattr(request.state, "user_id", None)
	role = getattr(request.state, "role", None)
	role_value = getattr(role, "value", role)
	role_normalizado = "".join(
		caractere
		for caractere in unicodedata.normalize("NFKD", str(role_value or "").upper())
		if not unicodedata.combining(caractere)
	)
	if not isinstance(user_id, int) or user_id < 1:
		raise HTTPException(status_code=401, detail="Autenticação obrigatória.")
	if role_normalizado != papel_esperado:
		raise HTTPException(status_code=403, detail="Perfil sem permissão para esta operação.")
	return user_id


def get_citizen_id(request: Request) -> int:
	"""Obtém o titular autenticado."""
	return _identidade(request, "CIDADAO")


def get_company_id(request: Request) -> int:
	"""Obtém a empresa autenticada."""
	return _identidade(request, "EMPRESA")


def _client_ip(request: Request) -> str | None:
	return request.client.host if request.client else None


@router.post("", response_model=ConsentimentoResposta, status_code=201)
def conceder(
	dados: ConcederAcessoEntrada,
	request: Request,
	cidadao_id: Annotated[int, Depends(get_citizen_id)],
	session: Annotated[Session, Depends(get_db)],
) -> ConsentimentoResposta:
	"""Concede acesso temporário da empresa a um documento próprio."""
	try:
		return conceder_acesso(
			session,
			cidadao_id=cidadao_id,
			documento_id=dados.documento_id,
			empresa_id=dados.empresa_id,
			expira_em=dados.expira_em,
			ip=_client_ip(request),
		)
	except LookupError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
	except ValueError as error:
		raise HTTPException(status_code=409, detail=str(error)) from error


@router.delete("/{consentimento_id}", status_code=204)
def revogar(
	consentimento_id: int,
	request: Request,
	cidadao_id: Annotated[int, Depends(get_citizen_id)],
	session: Annotated[Session, Depends(get_db)],
) -> Response:
	"""Revoga uma concessão pertencente ao titular autenticado."""
	try:
		revogar_acesso(
			session,
			cidadao_id=cidadao_id,
			consentimento_id=consentimento_id,
			ip=_client_ip(request),
		)
	except LookupError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
	except ValueError as error:
		raise HTTPException(status_code=409, detail=str(error)) from error
	return Response(status_code=204)


@router.get("", response_model=list[AcessoAtivoResposta])
def listar_acessos(
	request: Request,
	cidadao_id: Annotated[int, Depends(get_citizen_id)],
	session: Annotated[Session, Depends(get_db)],
) -> list[AcessoAtivoResposta]:
	"""Lista empresas com acesso atualmente ativo aos documentos do titular."""
	return [
		AcessoAtivoResposta.model_validate(consent)
		for consent in listar_acessos_ativos(
			session,
			cidadao_id=cidadao_id,
			ip=_client_ip(request),
		)
	]


@router.get("/documents/{documento_id}/content", response_model=ConteudoCompartilhadoResposta)
def consultar_conteudo(
	documento_id: int,
	request: Request,
	background_tasks: BackgroundTasks,
	empresa_id: Annotated[int, Depends(get_company_id)],
	session: Annotated[Session, Depends(get_db)],
) -> ConteudoCompartilhadoResposta | Response:
	"""Retorna OCR e metadados somente enquanto o consentimento estiver ativo."""
	try:
		document = obter_documento_compartilhado(
			session,
			empresa_id=empresa_id,
			documento_id=documento_id,
			ip=_client_ip(request),
		)
	except LookupError as error:
		background_tasks.add_task(
			notificar_tentativas_suspeitas,
			_client_ip(request),
			request.app.state.audit_session_factory,
		)
		return JSONResponse(
			status_code=404,
			content={"detail": str(error)},
			background=background_tasks,
		)
	return ConteudoCompartilhadoResposta(
		documento_id=document.id,
		nome_arquivo=document.nome_arquivo,
		content_type=document.content_type,
		tamanho_bytes=document.tamanho_bytes,
		tipo_documento=document.tipo_documento,
		nome_extraido=document.nome_extraido,
		data_extraida=document.data_extraida,
		emissor_extraido=document.emissor_extraido,
		conteudo_ocr=document.texto_ocr,
		download_url=f"/consent/documents/{document.id}/download",
	)


@router.get("/documents/{documento_id}/download")
def baixar_documento(
	documento_id: int,
	request: Request,
	background_tasks: BackgroundTasks,
	empresa_id: Annotated[int, Depends(get_company_id)],
	session: Annotated[Session, Depends(get_db)],	
	storage: Annotated[StorageService, Depends(get_storage_service)],
) -> Response:
	"""Entrega o arquivo original apenas com consentimento ativo."""
	try:
		document = obter_documento_compartilhado(
			session,
			empresa_id=empresa_id,
			documento_id=documento_id,
			ip=_client_ip(request),
			acao="consent.documento_baixado",
		)
		content = storage.read(document.storage_key)
	except LookupError as error:
		background_tasks.add_task(
			notificar_tentativas_suspeitas,
			_client_ip(request),
			request.app.state.audit_session_factory,
		)
		return JSONResponse(
			status_code=404,
			content={"detail": str(error)},
			background=background_tasks,
		)
	except FileNotFoundError as error:
		raise HTTPException(status_code=404, detail="Arquivo não encontrado.") from error
	return Response(
		content=content,
		media_type=document.content_type,
		headers={
			"Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.nome_arquivo)}"
		},
	)