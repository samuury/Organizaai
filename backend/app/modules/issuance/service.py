"""Emissão, hashing, QR Code, lote e revogação de documentos."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from io import BytesIO
from typing import Callable
from contextlib import AbstractContextManager

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.audit.service import registrar_auditoria
from app.modules.issuance.models import IssuanceBatch, IssuedDocument
from app.modules.issuance.schemas import EmissaoDocumentoEntrada


def calcular_hash(conteudo: dict[str, object]) -> str:
	"""Calcula SHA-256 sobre JSON canônico do conteúdo emitido."""
	canonical_content = json.dumps(
		conteudo,
		ensure_ascii=False,
		sort_keys=True,
		separators=(",", ":"),
		allow_nan=False,
	).encode("utf-8")
	return hashlib.sha256(canonical_content).hexdigest()


def url_verificacao(codigo: str) -> str:
	"""Monta a URL pública que será codificada no QR Code."""
	return f"{settings.api_public_url.rstrip('/')}/verificar/{codigo}"


def gerar_qr_code(url: str) -> bytes:
	"""Gera uma imagem PNG de QR Code para a URL de verificação."""
	qr = qrcode.QRCode(
		version=None,
		error_correction=ERROR_CORRECT_M,
		box_size=8,
		border=4,
	)
	qr.add_data(url)
	qr.make(fit=True)
	image = qr.make_image(fill_color="black", back_color="white")
	image_buffer = BytesIO()
	image.save(image_buffer, format="PNG")
	return image_buffer.getvalue()


def emitir_documento(
	session: Session,
	*,
	instituicao_id: int,
	dados: EmissaoDocumentoEntrada,
	emissor: str | None = None,
	ip: str | None = None,
	lote_id: str | None = None,
	linha_lote: int | None = None,
) -> IssuedDocument:
	"""Emite um documento, calcula seu hash e grava seu QR Code."""
	codigo = uuid.uuid4().hex
	content_hash = calcular_hash(dados.conteudo)
	verification_url = url_verificacao(codigo)
	document = IssuedDocument(
		instituicao_id=instituicao_id,
		emissor=emissor or f"Instituição #{instituicao_id}",
		usuario_id=dados.usuario_id,
		lote_id=lote_id,
		linha_lote=linha_lote,
		titulo=dados.titulo,
		tipo_documento=dados.tipo_documento,
		conteudo=dados.conteudo,
		codigo=codigo,
		hash_sha256=content_hash,
		qr_code_png=gerar_qr_code(verification_url),
	)
	try:
		session.add(document)
		session.flush()
		registrar_auditoria(
			session,
			usuario_id=instituicao_id,
			acao="issuance.documento_emitido",
			entidade="issued_documents",
			entidade_id=document.id,
			dados_depois={"tipo_documento": dados.tipo_documento, "hash_sha256": content_hash},
			ip=ip,
		)
		session.commit()
		session.refresh(document)
	except Exception:
		session.rollback()
		raise
	return document


def obter_documento_da_instituicao(
	session: Session, *, instituicao_id: int, codigo: str
) -> IssuedDocument:
	"""Busca um documento emitido pela instituição informada."""
	document = session.scalar(
		select(IssuedDocument).where(
			IssuedDocument.instituicao_id == instituicao_id,
			IssuedDocument.codigo == codigo,
		)
	)
	if document is None:
		raise LookupError("Documento não encontrado.")
	return document


def revogar_documento(
	session: Session,
	*,
	instituicao_id: int,
	codigo: str,
	motivo: str | None,
	ip: str | None = None,
) -> IssuedDocument:
	"""Revoga um documento da instituição e registra a alteração."""
	document = obter_documento_da_instituicao(
		session, instituicao_id=instituicao_id, codigo=codigo
	)
	if document.estado == "revogado":
		raise ValueError("O documento já foi revogado.")
	document.estado = "revogado"
	document.revogado_em = datetime.now(timezone.utc)
	document.motivo_revogacao = motivo.strip() if motivo else None
	registrar_auditoria(
		session,
		usuario_id=instituicao_id,
		acao="issuance.documento_revogado",
		entidade="issued_documents",
		entidade_id=document.id,
		dados_antes={"estado": "emitido"},
		dados_depois={"estado": "revogado"},
		ip=ip,
	)
	session.commit()
	session.refresh(document)
	return document


def processar_lote(
	lote_id: str,
	instituicao_id: int,
	registros: list[tuple[int, EmissaoDocumentoEntrada]],
	ip: str | None,
	session_factory: Callable[[], AbstractContextManager[Session]] | None = None,
) -> None:
	"""Emite em sequência os registros válidos de um lote em background."""
	factory = session_factory or SessionLocal
	with factory() as session:
		batch = session.get(IssuanceBatch, lote_id)
		if batch is None:
			return
		batch.estado = "processando"
		session.commit()

		for line_number, payload in registros:
			try:
				emitir_documento(
					session,
					instituicao_id=instituicao_id,
					emissor=batch.emissor,
					dados=payload,
					ip=ip,
					lote_id=lote_id,
					linha_lote=line_number,
				)
			except Exception:
				session.rollback()
				batch = session.get(IssuanceBatch, lote_id)
				if batch is None:
					return
				processing_errors = list(batch.erros_processamento)
				processing_errors.append(
					{"linha": line_number, "erros": ["Falha interna ao emitir este documento."]}
				)
				batch.erros_processamento = processing_errors
				try:
					registrar_auditoria(
						session,
						usuario_id=instituicao_id,
						acao="issuance.linha_lote_falhou",
						entidade="issuance_batches",
						entidade_id=lote_id,
						dados_depois={"linha": line_number},
						ip=ip,
					)
					session.commit()
				except Exception:
					session.rollback()

		batch = session.get(IssuanceBatch, lote_id)
		if batch is None:
			return
		has_errors = bool(batch.erros_validacao or batch.erros_processamento)
		batch.estado = "concluido_com_erros" if has_errors else "concluido"
		batch.finalizado_em = datetime.now(timezone.utc)
		total_linhas = batch.total_linhas
		validas = batch.validas
		erros = len(batch.erros_validacao) + len(batch.erros_processamento)
		session.commit()
		if has_errors:
			from app.core.notifications import notificar_falha_lote

			notificar_falha_lote(lote_id, total_linhas, validas, erros)