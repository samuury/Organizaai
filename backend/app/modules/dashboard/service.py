"""Consultas agregadas e rápidas do dashboard."""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from app.modules.dashboard.schemas import DashboardResumoResposta, TendenciaDiaria
from app.modules.issuance.models import IssuedDocument

PERIODO_DIAS = 30
_ACTIONS_VERIFICATION = (
	"verification.codigo_valido",
	"verification.codigo_invalido",
	"verification.codigo_revogado",
)


def _contagens_por_dia(rows: list[tuple[date | str, int]]) -> dict[date, int]:
	return {
		day if isinstance(day, date) else date.fromisoformat(day): int(count)
		for day, count in rows
	}


def obter_resumo(session: Session, *, hoje: date | None = None) -> DashboardResumoResposta:
	"""Conta documentos, verificações e usuários ativos no período recente."""
	current_date = hoje or datetime.now(timezone.utc).date()
	start_date = current_date - timedelta(days=PERIODO_DIAS - 1)
	start_datetime = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
	next_datetime = datetime.combine(current_date + timedelta(days=1), time.min, tzinfo=timezone.utc)

	documents_issued = session.scalar(select(func.count()).select_from(IssuedDocument)) or 0
	verification_count = (
		session.scalar(
			select(func.count())
			.select_from(AuditLog)
			.where(
				AuditLog.acao.in_(_ACTIONS_VERIFICATION),
				AuditLog.criado_em >= start_datetime,
				AuditLog.criado_em < next_datetime,
			)
		)
		or 0
	)
	active_users = (
		session.scalar(
			select(func.count(func.distinct(AuditLog.usuario_id)))
			.where(
				AuditLog.usuario_id.is_not(None),
				AuditLog.criado_em >= start_datetime,
				AuditLog.criado_em < next_datetime,
			)
		)
		or 0
	)

	document_daily = _contagens_por_dia(
		list(
			session.execute(
				select(func.date(IssuedDocument.emitido_em), func.count())
			.where(
				IssuedDocument.emitido_em >= start_datetime,
				IssuedDocument.emitido_em < next_datetime,
			)
				.group_by(func.date(IssuedDocument.emitido_em))
			).all()
		)
	)
	verification_daily = _contagens_por_dia(
		list(
			session.execute(
				select(func.date(AuditLog.criado_em), func.count())
			.where(
				AuditLog.acao.in_(_ACTIONS_VERIFICATION),
				AuditLog.criado_em >= start_datetime,
				AuditLog.criado_em < next_datetime,
			)
				.group_by(func.date(AuditLog.criado_em))
			).all()
		)
	)
	tendency = [
		TendenciaDiaria(
			data=start_date + timedelta(days=offset),
			documentos_emitidos=int(document_daily.get(start_date + timedelta(days=offset), 0)),
			verificacoes=int(verification_daily.get(start_date + timedelta(days=offset), 0)),
		)
		for offset in range(PERIODO_DIAS)
	]
	return DashboardResumoResposta(
		documentos_emitidos=int(documents_issued),
		verificacoes=int(verification_count),
		usuarios_ativos=int(active_users),
		periodo_dias=PERIODO_DIAS,
		tendencia=tendency,
	)