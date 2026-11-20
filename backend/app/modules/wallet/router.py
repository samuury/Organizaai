"""Rotas de upload, consulta e manutenção da carteira digital."""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.modules.audit.service import registrar_auditoria
from app.modules.wallet.models import WalletDocument
from app.modules.wallet.processing import processar_documento
from app.modules.wallet.schemas import DocumentoCorrecao, DocumentoResposta
from app.modules.wallet.service import (
	ArquivoMuitoGrandeError,
	FormatoDocumentoInvalidoError,
	corrigir_documento,
	criar_documento,
	excluir_documento,
	listar_documentos,
	obter_documento,
)
from app.modules.wallet.storage import LocalStorageService, StorageService

router = APIRouter(prefix="/wallet/documents", tags=["wallet"])


def get_current_user_id(request: Request) -> int:
	"""Obtém a identidade definida pelo middleware de autenticação."""
	user_id = getattr(request.state, "user_id", None)
	if not isinstance(user_id, int) or user_id < 1:
		raise HTTPException(status_code=401, detail="Autenticação obrigatória.")
	return user_id


def get_storage_service() -> StorageService:
	"""Fornece a implementação local substituível por armazenamento remoto."""
	return LocalStorageService(settings.storage_path)


def _client_ip(request: Request) -> str | None:
	return request.client.host if request.client else None


@router.post("", response_model=DocumentoResposta, status_code=202)
async def upload_documento(
	background_tasks: BackgroundTasks,
	request: Request,
	file: Annotated[UploadFile, File()],
	user_id: Annotated[int, Depends(get_current_user_id)],
	session: Annotated[Session, Depends(get_db)],
	storage: Annotated[StorageService, Depends(get_storage_service)],
) -> WalletDocument:
	"""Recebe o arquivo e agenda OCR/classificação em segundo plano."""
	content = await file.read(10 * 1024 * 1024 + 1)
	try:
		document = criar_documento(
			session,
			storage,
			usuario_id=user_id,
			filename=file.filename,
			content=content,
			ip=_client_ip(request),
		)
	except ArquivoMuitoGrandeError as error:
		raise HTTPException(status_code=413, detail=str(error)) from error
	except FormatoDocumentoInvalidoError as error:
		raise HTTPException(status_code=415, detail=str(error)) from error

	background_tasks.add_task(processar_documento, document.id)
	return document


@router.get("", response_model=list[DocumentoResposta])
def listar(
	request: Request,
	user_id: Annotated[int, Depends(get_current_user_id)],
	session: Annotated[Session, Depends(get_db)],
	busca: Annotated[str | None, Query(max_length=200)] = None,
	limite: Annotated[int, Query(ge=1, le=100)] = 20,
	deslocamento: Annotated[int, Query(ge=0)] = 0,
) -> list[WalletDocument]:
	"""Lista documentos próprios e oferece busca textual em português."""
	return listar_documentos(
		session,
		usuario_id=user_id,
		query=busca,
		limite=limite,
		deslocamento=deslocamento,
		ip=_client_ip(request),
	)


@router.get("/{document_id}", response_model=DocumentoResposta)
def obter(
	document_id: int,
	request: Request,
	user_id: Annotated[int, Depends(get_current_user_id)],
	session: Annotated[Session, Depends(get_db)],
) -> WalletDocument:
	"""Obtém os metadados de um documento próprio."""
	try:
		document = obter_documento(session, usuario_id=user_id, document_id=document_id)
	except LookupError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
	registrar_auditoria(
		session,
		usuario_id=user_id,
		acao="wallet.documento_consultado",
		entidade="wallet_documents",
		entidade_id=document.id,
		ip=_client_ip(request),
	)
	session.commit()
	return document


@router.get("/{document_id}/download")
def download_documento(
	document_id: int,
	request: Request,
	user_id: Annotated[int, Depends(get_current_user_id)],
	session: Annotated[Session, Depends(get_db)],
	storage: Annotated[StorageService, Depends(get_storage_service)],
) -> Response:
	"""Baixa o arquivo original e registra o acesso."""
	try:
		document = obter_documento(session, usuario_id=user_id, document_id=document_id)
		content = storage.read(document.storage_key)
	except LookupError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
	except FileNotFoundError as error:
		raise HTTPException(status_code=404, detail="Arquivo não encontrado.") from error
	registrar_auditoria(
		session,
		usuario_id=user_id,
		acao="wallet.documento_baixado",
		entidade="wallet_documents",
		entidade_id=document.id,
		ip=_client_ip(request),
	)
	session.commit()
	return Response(
		content=content,
		media_type=document.content_type,
		headers={
			"Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.nome_arquivo)}"
		},
	)


@router.patch("/{document_id}", response_model=DocumentoResposta)
def corrigir(
	document_id: int,
	correcao: DocumentoCorrecao,
	request: Request,
	user_id: Annotated[int, Depends(get_current_user_id)],
	session: Annotated[Session, Depends(get_db)],
) -> WalletDocument:
	"""Permite corrigir os dados extraídos pelo OCR."""
	changes = correcao.model_dump(exclude_unset=True)
	if not changes:
		raise HTTPException(status_code=422, detail="Informe ao menos um campo para corrigir.")
	try:
		return corrigir_documento(
			session,
			usuario_id=user_id,
			document_id=document_id,
			changes=changes,
			ip=_client_ip(request),
		)
	except LookupError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/{document_id}", status_code=204)
def excluir(
	document_id: int,
	request: Request,
	user_id: Annotated[int, Depends(get_current_user_id)],
	session: Annotated[Session, Depends(get_db)],
	storage: Annotated[StorageService, Depends(get_storage_service)],
) -> Response:
	"""Exclui um documento próprio e o respectivo arquivo."""
	try:
		excluir_documento(
			session,
			storage,
			usuario_id=user_id,
			document_id=document_id,
			ip=_client_ip(request),
		)
	except LookupError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
	return Response(status_code=204)