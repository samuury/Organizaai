"""Envio de alertas críticos por SMTP e webhook assinado."""

import hashlib
import hmac
import json
import logging
import smtplib
import time
import uuid
from contextlib import AbstractContextManager
from typing import Callable
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.audit.models import AuditLog

logger = logging.getLogger(__name__)
_SUSPICIOUS_ACTIONS = (
	"verification.codigo_invalido",
	"verification.rate_limited",
	"consent.documento_acesso_negado",
)
SessionFactory = Callable[[], AbstractContextManager[Session]]


def assinatura_webhook(secret: str, timestamp: str, body: bytes) -> str:
	"""Assina timestamp e corpo com HMAC-SHA256."""
	signed_content = timestamp.encode("ascii") + b"." + body
	digest = hmac.new(secret.encode("utf-8"), signed_content, hashlib.sha256).hexdigest()
	return f"sha256={digest}"


def enviar_alerta_critico(evento: str, detalhes: dict[str, int | str]) -> None:
	"""Entrega um alerta sem incluir conteúdo de documentos ou dados pessoais."""
	payload = {
		"id": uuid.uuid4().hex,
		"tipo": evento,
		"severidade": "critica",
		"ocorrido_em": datetime.now(timezone.utc).isoformat(),
		"detalhes": detalhes,
	}
	body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
		"utf-8"
	)

	if settings.critical_webhook_url and settings.critical_webhook_secret:
		timestamp = str(int(time.time()))
		headers = {
			"Content-Type": "application/json",
			"X-Organiza-Timestamp": timestamp,
			"X-Organiza-Signature": assinatura_webhook(
				settings.critical_webhook_secret, timestamp, body
			),
		}
		try:
			response = httpx.post(
				settings.critical_webhook_url,
				content=body,
				headers=headers,
				timeout=5.0,
			)
			response.raise_for_status()
		except httpx.HTTPError:
			logger.error("Falha na entrega do alerta crítico ao webhook configurado.")

	if settings.smtp_host and settings.smtp_from and settings.smtp_to:
		message = EmailMessage()
		message["Subject"] = f"[Organiza AI] Alerta crítico: {evento}"
		message["From"] = settings.smtp_from
		recipients = [recipient.strip() for recipient in settings.smtp_to.split(",") if recipient.strip()]
		message["To"] = ", ".join(recipients)
		message.set_content(json.dumps(payload, ensure_ascii=False, indent=2))
		try:
			with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5.0) as client:
				if settings.smtp_starttls:
					client.starttls()
				if settings.smtp_username:
					client.login(settings.smtp_username, settings.smtp_password or "")
				client.send_message(message)
		except (OSError, smtplib.SMTPException):
			logger.error("Falha na entrega do alerta crítico por e-mail.")


def notificar_falha_lote(
	lote_id: str,
	total_linhas: int,
	validas: int,
	erros: int,
) -> None:
	"""Notifica falha total ou parcial de um lote de emissão."""
	enviar_alerta_critico(
		"falha_lote_emissao",
		{
			"lote_id": lote_id,
			"total_linhas": total_linhas,
			"validas": validas,
			"erros": erros,
		},
	)


def notificar_falha_ocr_em_massa(session_factory: SessionFactory | None = None) -> None:
	"""Notifica ao atingir o limiar de falhas de OCR na janela configurada."""
	window_start = datetime.now(timezone.utc) - timedelta(minutes=settings.alert_window_minutes)
	with (session_factory or SessionLocal)() as session:
		failure_count = session.scalar(
			select(func.count())
			.select_from(AuditLog)
			.where(
				AuditLog.acao == "wallet.ocr_falhou",
				AuditLog.criado_em >= window_start,
			)
		)
	if failure_count == settings.ocr_mass_failure_threshold:
		enviar_alerta_critico(
			"falha_ocr_em_massa",
			{
				"falhas": failure_count,
				"janela_minutos": settings.alert_window_minutes,
			},
		)


def notificar_tentativas_suspeitas(
	ip: str | None,
	session_factory: SessionFactory | None = None,
) -> None:
	"""Notifica tentativas suspeitas repetidas sem expor o IP em claro."""
	if not ip:
		return
	window_start = datetime.now(timezone.utc) - timedelta(minutes=settings.alert_window_minutes)
	with (session_factory or SessionLocal)() as session:
		attempt_count = session.scalar(
			select(func.count())
			.select_from(AuditLog)
			.where(
				AuditLog.ip == ip,
				AuditLog.acao.in_(_SUSPICIOUS_ACTIONS),
				AuditLog.criado_em >= window_start,
			)
		)
	if attempt_count == settings.suspicious_access_threshold:
		ip_fingerprint = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]
		enviar_alerta_critico(
			"tentativas_de_acesso_suspeitas",
			{
				"tentativas": attempt_count,
				"janela_minutos": settings.alert_window_minutes,
				"ip_fingerprint": ip_fingerprint,
			},
		)