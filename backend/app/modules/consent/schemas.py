"""Schemas de concessão de acesso e conteúdo compartilhado."""

from datetime import date, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class ConcederAcessoEntrada(BaseModel):
	"""Dados necessários para conceder acesso a uma empresa."""

	documento_id: int = Field(gt=0)
	empresa_id: int = Field(gt=0)
	expira_em: AwareDatetime


class ConsentimentoResposta(BaseModel):
	"""Concessão registrada pelo titular."""

	model_config = ConfigDict(from_attributes=True)

	id: int
	documento_id: int
	empresa_id: int
	expira_em: datetime
	revogado_em: datetime | None
	criado_em: datetime


class AcessoAtivoResposta(BaseModel):
	"""Acesso ativo visível ao titular."""

	id: int
	documento_id: int
	empresa_id: int
	expira_em: datetime
	criado_em: datetime


class ConteudoCompartilhadoResposta(BaseModel):
	"""Metadados e texto OCR disponíveis à empresa consentida."""

	documento_id: int
	nome_arquivo: str
	content_type: str
	tamanho_bytes: int
	tipo_documento: str | None
	nome_extraido: str | None
	data_extraida: date | None
	emissor_extraido: str | None
	conteudo_ocr: str | None
	download_url: str