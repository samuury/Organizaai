"""Schemas de entrada e saída da carteira digital."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TipoDocumento = Literal["diploma", "certidao", "comprovante"]


class DocumentoResposta(BaseModel):
	"""Metadados e resultado do processamento de um documento."""

	model_config = ConfigDict(from_attributes=True)

	id: int
	nome_arquivo: str
	content_type: str
	tamanho_bytes: int
	estado_processamento: str
	tipo_documento: TipoDocumento | None
	nome_extraido: str | None
	data_extraida: date | None
	emissor_extraido: str | None
	erro_processamento: str | None
	criado_em: datetime
	atualizado_em: datetime


class DocumentoCorrecao(BaseModel):
	"""Campos extraídos e metadados que o usuário pode revisar e corrigir."""

	model_config = ConfigDict(extra="forbid")

	nome_arquivo: str | None = Field(default=None, min_length=1, max_length=255)
	tipo_documento: TipoDocumento | None = None
	nome_extraido: str | None = Field(default=None, max_length=255)
	data_extraida: date | None = None
	emissor_extraido: str | None = Field(default=None, max_length=255)

	@field_validator("nome_arquivo", "nome_extraido", "emissor_extraido")
	@classmethod
	def normalizar_texto(cls, value: str | None) -> str | None:
		"""Remove espaços externos das correções textuais."""
		return value.strip() if value is not None else None