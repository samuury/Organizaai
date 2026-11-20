"""Rotas de emissão, consulta de lotes, QR Codes e revogação."""

import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.modules.audit.service import registrar_auditoria
from app.modules.issuance.batch import FormatoLoteInvalidoError, validar_arquivo_lote
from app.modules.issuance.models import IssuanceBatch, IssuedDocument
from app.modules.issuance.schemas import (
	DocumentoEmitidoResposta,
	DocumentoLoteResposta,
	EmissaoDocumentoEntrada,
	ErroLinha,
	RelatorioLote,
	ResultadoLote,
	RevogacaoEntrada,
)
from app.modules.issuance.service import (
	emitir_documento,
	obter_documento_da_instituicao,
	processar_lote,
	revogar_documento,
	url_verificacao,
)

MAX_BATCH_SIZE = 10 * 1024 * 1024
router = APIRouter(prefix="/issuance", tags=["issuance"])


def get_institution_id(request: Request) -> int:
	"""Obtém a instituição autenticada do contexto definido pelo middleware."""
	user_id = getattr(request.state, "user_id", None)
	role = getattr(request.state, "role", None)
	role_value = getattr(role, "value", role)
	normalized_role = "".join(
		character
		for character in unicodedata.normalize("NFKD", str(role_value or "").upper())
		if not unicodedata.combining(character)
	)
	if not isinstance(user_id, int) or user_id < 1:
		raise HTTPException(status_code=401, detail="Autenticação obrigatória.")
	if normalized_role != "INSTITUICAO":
		raise HTTPException(status_code=403, detail="Apenas instituições podem emitir documentos.")
	return user_id


def _client_ip(request: Request) -> str | None:
	return request.client.host if request.client else None


def _institution_name(request: Request, institution_id: int) -> str:
	name = getattr(request.state, "institution_name", None)
	if isinstance(name, str) and name.strip():
		return name.strip()[:255]
	return f"Instituição #{institution_id}"


def _document_response(document: IssuedDocument) -> DocumentoEmitidoResposta:
	return DocumentoEmitidoResposta(
		id=document.id,
		usuario_id=document.usuario_id,
		titulo=document.titulo,
		tipo_documento=document.tipo_documento,
		codigo=document.codigo,
		hash_sha256=document.hash_sha256,
		estado=document.estado,
		emitido_em=document.emitido_em,
		revogado_em=document.revogado_em,
		verification_url=url_verificacao(document.codigo),
		qr_code_url=f"/issuance/{document.codigo}/qr",
	)


@router.post("", response_model=DocumentoEmitidoResposta, status_code=201)
def emitir(
	dados: EmissaoDocumentoEntrada,
	request: Request,
	instituicao_id: Annotated[int, Depends(get_institution_id)],
	session: Annotated[Session, Depends(get_db)],
) -> DocumentoEmitidoResposta:
	"""Emite um documento individual com hash e QR Code."""
	document = emitir_documento(
		session,
		instituicao_id=instituicao_id,
		emissor=_institution_name(request, instituicao_id),
		dados=dados,
		ip=_client_ip(request),
	)
	return _document_response(document)


@router.post("/batch", response_model=ResultadoLote, status_code=202)
async def emitir_lote(
	background_tasks: BackgroundTasks,
	request: Request,
	file: Annotated[UploadFile, File()],
	instituicao_id: Annotated[int, Depends(get_institution_id)],
	session: Annotated[Session, Depends(get_db)],
) -> ResultadoLote:
	"""Valida cada registro do CSV/JSON e agenda os válidos em background."""
	content = await file.read(MAX_BATCH_SIZE + 1)
	if len(content) > MAX_BATCH_SIZE:
		raise HTTPException(status_code=413, detail="O arquivo de lote excede 10 MB.")
	try:
		validation = validar_arquivo_lote(file.filename, content)
	except FormatoLoteInvalidoError as error:
		raise HTTPException(status_code=415, detail=str(error)) from error

	batch_id = uuid.uuid4().hex
	ip = _client_ip(request)
	validation_errors = [error.model_dump(mode="json") for error in validation.erros]
	initial_status = "pendente"
	batch = IssuanceBatch(
		id=batch_id,
		instituicao_id=instituicao_id,
		emissor=_institution_name(request, instituicao_id),
		estado=initial_status,
		total_linhas=validation.total_linhas,
		validas=len(validation.registros),
		erros_validacao=validation_errors,
		erros_processamento=[],
		finalizado_em=None,
	)
	session.add(batch)
	session.flush()
	registrar_auditoria(
		session,
		usuario_id=instituicao_id,
		acao="issuance.lote_enviado",
		entidade="issuance_batches",
		entidade_id=batch_id,
		dados_depois={
			"total_linhas": validation.total_linhas,
			"validas": len(validation.registros),
			"erros": len(validation.erros),
		},
		ip=ip,
	)
	session.commit()
	background_tasks.add_task(
		processar_lote,
		batch_id,
		instituicao_id,
		validation.registros,
		ip,
		getattr(request.app.state, "audit_session_factory", None),
	)
	return ResultadoLote(
		lote_id=batch_id,
		estado=initial_status,
		total_linhas=validation.total_linhas,
		validas=len(validation.registros),
		erros=validation.erros,
	)


@router.get("/batch/{batch_id}", response_model=RelatorioLote)
def consultar_lote(
	batch_id: str,
	request: Request,
	instituicao_id: Annotated[int, Depends(get_institution_id)],
	session: Annotated[Session, Depends(get_db)],
) -> RelatorioLote:
	"""Retorna estado, erros e códigos gerados para um lote da instituição."""
	batch = session.get(IssuanceBatch, batch_id)
	if batch is None or batch.instituicao_id != instituicao_id:
		raise HTTPException(status_code=404, detail="Lote não encontrado.")
	documents = session.scalars(
		select(IssuedDocument)
		.where(IssuedDocument.lote_id == batch_id)
		.order_by(IssuedDocument.linha_lote)
	).all()
	registrar_auditoria(
		session,
		usuario_id=instituicao_id,
		acao="issuance.lote_consultado",
		entidade="issuance_batches",
		entidade_id=batch_id,
		ip=_client_ip(request),
	)
	session.commit()
	return RelatorioLote(
		lote_id=batch.id,
		estado=batch.estado,
		total_linhas=batch.total_linhas,
		validas=batch.validas,
		erros_validacao=[ErroLinha.model_validate(error) for error in batch.erros_validacao],
		erros_processamento=[ErroLinha.model_validate(error) for error in batch.erros_processamento],
		documentos=[
			DocumentoLoteResposta(
				linha=document.linha_lote,
				codigo=document.codigo,
				hash_sha256=document.hash_sha256,
				estado=document.estado,
				verification_url=url_verificacao(document.codigo),
				qr_code_url=f"/issuance/{document.codigo}/qr",
			)
			for document in documents
		],
	)


@router.get("/{codigo}/qr")
def obter_qr_code(
	codigo: str,
	request: Request,
	instituicao_id: Annotated[int, Depends(get_institution_id)],
	session: Annotated[Session, Depends(get_db)],
) -> Response:
	"""Retorna o QR Code PNG de um documento da instituição."""
	try:
		document = obter_documento_da_instituicao(
			session, instituicao_id=instituicao_id, codigo=codigo
		)
	except LookupError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
	registrar_auditoria(
		session,
		usuario_id=instituicao_id,
		acao="issuance.qr_consultado",
		entidade="issued_documents",
		entidade_id=document.id,
		ip=_client_ip(request),
	)
	session.commit()
	return Response(content=document.qr_code_png, media_type="image/png")


@router.post("/{codigo}/revoke", response_model=DocumentoEmitidoResposta)
def revogar(
	codigo: str,
	request: Request,
	instituicao_id: Annotated[int, Depends(get_institution_id)],
	session: Annotated[Session, Depends(get_db)],
	dados: RevogacaoEntrada | None = None,
) -> DocumentoEmitidoResposta:
	"""Revoga um documento emitido pela instituição autenticada."""
	try:
		document = revogar_documento(
			session,
			instituicao_id=instituicao_id,
			codigo=codigo,
			motivo=dados.motivo if dados else None,
			ip=_client_ip(request),
		)
	except LookupError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
	except ValueError as error:
		raise HTTPException(status_code=409, detail=str(error)) from error
	return _document_response(document)