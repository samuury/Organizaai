"""Testes de assinatura de webhook e alertas de falha crítica."""

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core import notifications
from app.core.notifications import assinatura_webhook, enviar_alerta_critico
from app.modules.audit.models import AuditLog


def test_assinatura_webhook_cobre_timestamp_e_corpo() -> None:
	secret = "segredo-de-teste"
	timestamp = "1795176000"
	body = b'{"tipo":"falha_lote_emissao"}'
	expected = hmac.new(
		secret.encode(),
		timestamp.encode() + b"." + body,
		hashlib.sha256,
	).hexdigest()

	assert assinatura_webhook(secret, timestamp, body) == f"sha256={expected}"


def test_webhook_recebe_payload_assinado_sem_dados_pessoais(monkeypatch) -> None:
	monkeypatch.setattr(notifications.settings, "critical_webhook_url", "https://example.test/hook")
	monkeypatch.setattr(notifications.settings, "critical_webhook_secret", "webhook-secret")
	monkeypatch.setattr(notifications.settings, "smtp_host", None)
	response = Mock()
	response.raise_for_status.return_value = None
	request_mock = Mock(return_value=response)
	monkeypatch.setattr(notifications.httpx, "post", request_mock)

	enviar_alerta_critico("falha_lote_emissao", {"lote_id": "batch-id", "erros": 2})

	kwargs = request_mock.call_args.kwargs
	timestamp = kwargs["headers"]["X-Organiza-Timestamp"]
	assert kwargs["headers"]["X-Organiza-Signature"] == assinatura_webhook(
		"webhook-secret", timestamp, kwargs["content"]
	)
	assert "nome" not in json.loads(kwargs["content"])


def test_ocr_dispara_alerta_ao_atingir_limiar(monkeypatch) -> None:
	engine = create_engine(
		"sqlite://",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	AuditLog.__table__.create(engine)
	factory = lambda: Session(engine)
	with factory() as session:
		failure_time = datetime.now(timezone.utc) - timedelta(seconds=2)
		session.add_all(
			[
				AuditLog(acao="wallet.ocr_falhou", entidade="wallet_documents", criado_em=failure_time),
				AuditLog(acao="wallet.ocr_falhou", entidade="wallet_documents", criado_em=failure_time),
			]
		)
		session.commit()
	monkeypatch.setattr(notifications.settings, "ocr_mass_failure_threshold", 2)
	monkeypatch.setattr(notifications.settings, "alert_window_minutes", 10)
	alert_mock = Mock()
	monkeypatch.setattr(notifications, "enviar_alerta_critico", alert_mock)

	notifications.notificar_falha_ocr_em_massa(factory)

	alert_mock.assert_called_once_with(
		"falha_ocr_em_massa", {"falhas": 2, "janela_minutos": 10}
	)
	engine.dispose()


def test_falha_de_lote_emite_resumo_sem_dados_dos_documentos(monkeypatch) -> None:
	alert_mock = Mock()
	monkeypatch.setattr(notifications, "enviar_alerta_critico", alert_mock)

	notifications.notificar_falha_lote("lote-123", total_linhas=8, validas=6, erros=2)

	alert_mock.assert_called_once_with(
		"falha_lote_emissao",
		{"lote_id": "lote-123", "total_linhas": 8, "validas": 6, "erros": 2},
	)


def test_acesso_suspeito_usa_fingerprint_ip_no_alerta(monkeypatch) -> None:
	engine = create_engine(
		"sqlite://",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	AuditLog.__table__.create(engine)
	factory = lambda: Session(engine)
	with factory() as session:
		attempt_time = datetime.now(timezone.utc) - timedelta(seconds=2)
		session.add_all(
			[
				AuditLog(
					acao="verification.codigo_invalido",
					entidade="issued_documents",
					ip="198.51.100.40",
					criado_em=attempt_time,
				)
				for _ in range(3)
			]
		)
		session.commit()
	monkeypatch.setattr(notifications.settings, "suspicious_access_threshold", 3)
	monkeypatch.setattr(notifications.settings, "alert_window_minutes", 10)
	alert_mock = Mock()
	monkeypatch.setattr(notifications, "enviar_alerta_critico", alert_mock)

	notifications.notificar_tentativas_suspeitas("198.51.100.40", factory)

	event, details = alert_mock.call_args.args
	assert event == "tentativas_de_acesso_suspeitas"
	assert details["tentativas"] == 3
	assert details["ip_fingerprint"] != "198.51.100.40"
	engine.dispose()