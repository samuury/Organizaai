"""Validação linha a linha de arquivos de emissão em lote."""

import csv
import io
import json
from dataclasses import dataclass

from pydantic import ValidationError

from app.modules.issuance.schemas import EmissaoDocumentoEntrada, ErroLinha


class FormatoLoteInvalidoError(ValueError):
	"""O arquivo de lote não é CSV ou JSON válido."""


@dataclass(slots=True)
class ResultadoValidacaoLote:
	"""Registros aceitos e relatório de erros de um arquivo."""

	total_linhas: int
	registros: list[tuple[int, EmissaoDocumentoEntrada]]
	erros: list[ErroLinha]


def _formatar_erros(error: ValidationError) -> list[str]:
	return [
		f"{'.'.join(str(part) for part in detail['loc'])}: {detail['msg']}"
		for detail in error.errors(include_input=False)
	]


def _validar_registro(
	line_number: int,
	record: object,
	*,
	csv_record: bool = False,
) -> tuple[tuple[int, EmissaoDocumentoEntrada] | None, ErroLinha | None]:
	if not isinstance(record, dict):
		return None, ErroLinha(linha=line_number, erros=["O registro deve ser um objeto JSON."])

	data = dict(record)
	if csv_record:
		try:
			data["usuario_id"] = int(data.get("usuario_id", ""))
		except (TypeError, ValueError):
			pass
		try:
			data["conteudo"] = json.loads(data.get("conteudo", ""))
		except (json.JSONDecodeError, TypeError):
			return None, ErroLinha(
				linha=line_number,
				erros=["conteudo: deve conter um objeto JSON válido."],
			)

	try:
		return (line_number, EmissaoDocumentoEntrada.model_validate(data)), None
	except ValidationError as error:
		return None, ErroLinha(linha=line_number, erros=_formatar_erros(error))


def validar_arquivo_lote(filename: str | None, content: bytes) -> ResultadoValidacaoLote:
	"""Lê CSV/JSON e valida cada linha/registro sem interromper o lote."""
	if not filename:
		raise FormatoLoteInvalidoError("O arquivo precisa ter extensão .csv ou .json.")
	extension = filename.lower().rsplit(".", 1)[-1]
	if extension not in {"csv", "json"}:
		raise FormatoLoteInvalidoError("Envie um arquivo .csv ou .json.")
	try:
		text = content.decode("utf-8-sig")
	except UnicodeDecodeError as error:
		raise FormatoLoteInvalidoError("O arquivo deve usar codificação UTF-8.") from error

	if extension == "csv":
		return _validar_csv(text)
	return _validar_json(text)


def _validar_csv(text: str) -> ResultadoValidacaoLote:
	reader = csv.DictReader(io.StringIO(text))
	if not reader.fieldnames:
		return ResultadoValidacaoLote(
			total_linhas=0,
			registros=[],
			erros=[ErroLinha(linha=1, erros=["Cabeçalho CSV ausente."])],
		)
	valid_records: list[tuple[int, EmissaoDocumentoEntrada]] = []
	errors: list[ErroLinha] = []
	total_rows = 0
	try:
		for record in reader:
			if not any(value and value.strip() for value in record.values() if isinstance(value, str)):
				continue
			total_rows += 1
			line_number = reader.line_num
			valid_record, error = _validar_registro(line_number, record, csv_record=True)
			if valid_record:
				valid_records.append(valid_record)
			if error:
				errors.append(error)
	except csv.Error as error:
		errors.append(ErroLinha(linha=reader.line_num + 1, erros=[f"CSV inválido: {error}."]))
	if total_rows == 0 and not errors:
		errors.append(ErroLinha(linha=2, erros=["O arquivo não contém registros."]))
	return ResultadoValidacaoLote(total_rows, valid_records, errors)


def _validar_json(text: str) -> ResultadoValidacaoLote:
	try:
		data = json.loads(text)
	except json.JSONDecodeError as error:
		return ResultadoValidacaoLote(
			total_linhas=1,
			registros=[],
			erros=[ErroLinha(linha=error.lineno, erros=["JSON inválido."])],
		)
	if not isinstance(data, list):
		return ResultadoValidacaoLote(
			total_linhas=1,
			registros=[],
			erros=[ErroLinha(linha=1, erros=["O JSON deve conter uma lista de documentos."])],
		)
	valid_records: list[tuple[int, EmissaoDocumentoEntrada]] = []
	errors: list[ErroLinha] = []
	for line_number, record in enumerate(data, start=1):
		valid_record, error = _validar_registro(line_number, record)
		if valid_record:
			valid_records.append(valid_record)
		if error:
			errors.append(error)
	if not data:
		errors.append(ErroLinha(linha=1, erros=["O arquivo não contém registros."]))
	return ResultadoValidacaoLote(len(data), valid_records, errors)