"""Schemas de indicadores do dashboard."""

from datetime import date

from pydantic import BaseModel


class TendenciaDiaria(BaseModel):
	"""Contagens diárias usadas na visualização de atividade."""

	data: date
	documentos_emitidos: int
	verificacoes: int


class DashboardResumoResposta(BaseModel):
	"""Indicadores principais e tendência recente do sistema."""

	documentos_emitidos: int
	verificacoes: int
	usuarios_ativos: int
	periodo_dias: int
	tendencia: list[TendenciaDiaria]