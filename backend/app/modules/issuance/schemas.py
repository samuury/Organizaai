"""Schemas de entrada e saída da emissão de documentos."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TipoDocumentoEmitido = Literal["diploma", "certidao", "comprovante"]


class EmissaoDocumentoEntrada(BaseModel):
	"""Dados estruturados para emitir um documento."""

	model_config = ConfigDict(extra="forbid")

	usuario_id: int = Field(gt=0)
	titulo: str = Field(min_length=1, max_length=255)
	tipo_documento: TipoDocumentoEmitido
	conteudo: dict[str, Any]


class RevogacaoEntrada(BaseModel):
	"""Motivo opcional para revogar um documento emitido."""

	model_config = ConfigDict(extra="forbid")

	motivo: str | None = Field(default=None, max_length=1000)


class ErroLinha(BaseModel):
	"""Erros de validação associados a uma linha do lote."""

	linha: int
	erros: list[str]


class DocumentoEmitidoResposta(BaseModel):
	"""Metadados públicos do documento emitido."""

	model_config = ConfigDict(from_attributes=True)

	id: int
	usuario_id: int
	titulo: str
	tipo_documento: TipoDocumentoEmitido
	codigo: str
	hash_sha256: str
	estado: Literal["emitido", "revogado"]
	emitido_em: datetime
	revogado_em: datetime | None
	verification_url: str
	qr_code_url: str


class ResultadoLote(BaseModel):
	"""Relatório imediato da validação e do enfileiramento de um lote."""

	lote_id: str
	estado: str
	total_linhas: int
	validas: int
	erros: list[ErroLinha]


class DocumentoLoteResposta(BaseModel):
	"""Resultado de emissão de uma linha aceita do lote."""

	linha: int | None
	codigo: str
	hash_sha256: str
	estado: Literal["emitido", "revogado"]
	verification_url: str
	qr_code_url: str


class RelatorioLote(BaseModel):
	"""Estado consultável do processamento de um lote."""

	lote_id: str
	estado: str
	total_linhas: int
	validas: int
	erros_validacao: list[ErroLinha]
	erros_processamento: list[ErroLinha]
	documentos: list[DocumentoLoteResposta]


class VerificacaoPublicaResposta(BaseModel):
	"""Resultado público da verificação por código."""

	status: Literal["VALIDO", "INVALIDO", "REVOGADO"]
	emissor: str | None
	data_emissao: datetime | None