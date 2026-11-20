"""Regras de negócio e persistência da carteira digital."""

import re
import uuid
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.modules.audit.service import registrar_auditoria
from app.modules.wallet.models import WalletDocument
from app.modules.wallet.storage import StorageService

MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class ArquivoMuitoGrandeError(ValueError):
	"""O arquivo excede o limite permitido."""


class FormatoDocumentoInvalidoError(ValueError):
	"""O tipo ou conteúdo do arquivo não é suportado."""


def validar_upload(filename: str | None, content: bytes) -> tuple[str, str, str]:
	"""Valida tamanho, extensão e assinatura real do arquivo enviado."""
	if len(content) > MAX_DOCUMENT_SIZE:
		raise ArquivoMuitoGrandeError("O arquivo excede o limite de 10 MB.")
	if not filename or not content:
		raise FormatoDocumentoInvalidoError("O arquivo está vazio ou sem nome.")

	safe_filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
	safe_filename = _CONTROL_CHARS.sub("", safe_filename).strip()[:255]
	extension = PurePosixPath(safe_filename).suffix.lower()
	if extension not in ALLOWED_EXTENSIONS:
		raise FormatoDocumentoInvalidoError("Envie um arquivo PDF, JPG ou PNG.")

	if extension == ".pdf" and content.startswith(b"%PDF-"):
		return safe_filename, "application/pdf", ".pdf"
	if extension in {".jpg", ".jpeg"} and content.startswith(b"\xff\xd8\xff"):
		try:
			with Image.open(BytesIO(content)) as image:
				image.verify()
		except Exception as error:
			raise FormatoDocumentoInvalidoError("O arquivo JPG é inválido.") from error
		return safe_filename, "image/jpeg", ".jpg"
	if extension == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n"):
		try:
			with Image.open(BytesIO(content)) as image:
				image.verify()
		except Exception as error:
			raise FormatoDocumentoInvalidoError("O arquivo PNG é inválido.") from error
		return safe_filename, "image/png", ".png"
	raise FormatoDocumentoInvalidoError("A extensão não corresponde ao conteúdo do arquivo.")


def criar_documento(
	session: Session,
	storage: StorageService,
	*,
	usuario_id: int,
	filename: str | None,
	content: bytes,
	ip: str | None = None,
) -> WalletDocument:
	"""Armazena o arquivo e cria seu registro pendente de OCR."""
	safe_filename, content_type, extension = validar_upload(filename, content)
	storage_key = f"{uuid.uuid4().hex}{extension}"
	storage.save(storage_key, content)
	document = WalletDocument(
		usuario_id=usuario_id,
		nome_arquivo=safe_filename,
		storage_key=storage_key,
		content_type=content_type,
		tamanho_bytes=len(content),
	)
	try:
		session.add(document)
		session.flush()
		registrar_auditoria(
			session,
			usuario_id=usuario_id,
			acao="wallet.documento_enviado",
			entidade="wallet_documents",
			entidade_id=document.id,
			dados_depois={"content_type": content_type, "tamanho_bytes": len(content)},
			ip=ip,
		)
		session.commit()
		session.refresh(document)
	except Exception:
		session.rollback()
		storage.delete(storage_key)
		raise
	return document


def consulta_documentos(
	usuario_id: int, query: str | None = None
) -> Select[tuple[WalletDocument]]:
	"""Monta a consulta isolada por usuário e opcionalmente por full-text search."""
	statement = (
		select(WalletDocument)
		.where(WalletDocument.usuario_id == usuario_id)
		.order_by(WalletDocument.criado_em.desc())
	)
	if query and query.strip():
		statement = statement.where(
			WalletDocument.search_vector.op("@@")(
				func.plainto_tsquery("portuguese", query.strip())
			)
		)
	return statement


def listar_documentos(
	session: Session,
	*,
	usuario_id: int,
	query: str | None,
	limite: int,
	deslocamento: int,
	ip: str | None = None,
) -> list[WalletDocument]:
	"""Lista documentos do usuário com busca full-text opcional."""
	statement = consulta_documentos(usuario_id, query).limit(limite).offset(deslocamento)
	documents = list(session.scalars(statement).all())
	registrar_auditoria(
		session,
		usuario_id=usuario_id,
		acao="wallet.documentos_listados",
		entidade="wallet_documents",
		ip=ip,
	)
	session.commit()
	return documents


def obter_documento(session: Session, *, usuario_id: int, document_id: int) -> WalletDocument:
	"""Busca um documento pertencente ao usuário."""
	document = session.scalar(
		select(WalletDocument).where(
			WalletDocument.id == document_id,
			WalletDocument.usuario_id == usuario_id,
		)
	)
	if document is None:
		raise LookupError("Documento não encontrado.")
	return document


def corrigir_documento(
	session: Session,
	*,
	usuario_id: int,
	document_id: int,
	changes: dict[str, Any],
	ip: str | None = None,
) -> WalletDocument:
	"""Atualiza os campos extraídos e registra os campos corrigidos."""
	document = obter_documento(session, usuario_id=usuario_id, document_id=document_id)
	changed_fields = list(changes)
	for field, value in changes.items():
		setattr(document, field, value)
	registrar_auditoria(
		session,
		usuario_id=usuario_id,
		acao="wallet.documento_corrigido",
		entidade="wallet_documents",
		entidade_id=document.id,
		dados_depois={"campos_corrigidos": changed_fields},
		ip=ip,
	)
	session.commit()
	session.refresh(document)
	return document


def excluir_documento(
	session: Session,
	storage: StorageService,
	*,
	usuario_id: int,
	document_id: int,
	ip: str | None = None,
) -> None:
	"""Exclui um documento do usuário e seu arquivo armazenado."""
	document = obter_documento(session, usuario_id=usuario_id, document_id=document_id)
	storage_key = document.storage_key
	registrar_auditoria(
		session,
		usuario_id=usuario_id,
		acao="wallet.documento_excluido",
		entidade="wallet_documents",
		entidade_id=document.id,
		ip=ip,
	)
	session.delete(document)
	session.commit()
	storage.delete(storage_key)