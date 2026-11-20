"""Testes das regras de emissão institucional."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.modules.issuance.batch import validar_arquivo_lote
from app.modules.issuance.models import IssuedDocument
from app.modules.issuance.router import get_institution_id
from app.modules.issuance.schemas import EmissaoDocumentoEntrada
from app.modules.issuance.service import calcular_hash, emitir_documento, revogar_documento


def _request_with_state(state: dict[str, object]) -> Request:
	return Request(
		{
			"type": "http",
			"method": "POST",
			"path": "/issuance",
			"headers": [],
			"query_string": b"",
			"server": ("testserver", 80),
			"client": ("127.0.0.1", 1234),
			"state": state,
		}
	)


def _payload() -> EmissaoDocumentoEntrada:
	return EmissaoDocumentoEntrada(
		usuario_id=73,
		titulo="Diploma de graduação",
		tipo_documento="diploma",
		conteudo={"nome": "Ana Souza", "ano": 2023},
	)


def test_hash_sha256_usa_json_canonico() -> None:
	assert calcular_hash({"ano": 2023, "nome": "Ana"}) == calcular_hash(
		{"nome": "Ana", "ano": 2023}
	)
	assert len(calcular_hash({"nome": "Ana"})) == 64


def test_emissao_gera_codigo_hash_e_qr_png() -> None:
	session = Mock(spec=Session)

	def add_record(record: object) -> None:
		if isinstance(record, IssuedDocument):
			record.id = 18

	session.add.side_effect = add_record

	document = emitir_documento(session, instituicao_id=9, dados=_payload())

	assert document.id == 18
	assert len(document.codigo) == 32
	assert document.hash_sha256 == calcular_hash(_payload().conteudo)
	assert document.qr_code_png.startswith(b"\x89PNG\r\n\x1a\n")
	session.commit.assert_called_once()


def test_csv_valida_registros_e_preserva_linha_fisica() -> None:
	content = (
		b'usuario_id,titulo,tipo_documento,conteudo\n'
		b'73,Diploma,diploma,"{""ano"":2023}"\n'
		b'0,Certidao,certidao,"{""registro"":1}"\n'
	)

	result = validar_arquivo_lote("emissoes.csv", content)

	assert result.total_linhas == 2
	assert [line for line, _ in result.registros] == [2]
	assert result.erros[0].linha == 3
	assert any("usuario_id" in message for message in result.erros[0].erros)


def test_json_valida_registros_e_reporta_erro_por_indice() -> None:
	content = (
		b'[{"usuario_id":73,"titulo":"Diploma","tipo_documento":"diploma",'
		b'"conteudo":{"ano":2023}},'
		b'{"usuario_id":-1,"titulo":"Invalido","tipo_documento":"outro",'
		b'"conteudo":{}}]'
	)

	result = validar_arquivo_lote("emissoes.json", content)

	assert result.total_linhas == 2
	assert [line for line, _ in result.registros] == [1]
	assert result.erros[0].linha == 2
	assert len(result.erros[0].erros) == 2


def test_lote_rejeita_extensao_nao_suportada() -> None:
	with pytest.raises(ValueError):
		validar_arquivo_lote("emissoes.xlsx", b"")


def test_contexto_exige_perfil_instituicao() -> None:
	request = _request_with_state({"user_id": 9, "role": "INSTITUIÇÃO"})
	assert get_institution_id(request) == 9

	request = _request_with_state({"user_id": 9, "role": "CIDADÃO"})
	with pytest.raises(HTTPException) as error:
		get_institution_id(request)
	assert error.value.status_code == 403


def test_revogacao_altera_estado_e_registra_data() -> None:
	session = Mock(spec=Session)
	document = IssuedDocument(
		id=21,
		instituicao_id=9,
		usuario_id=73,
		titulo="Diploma",
		tipo_documento="diploma",
		conteudo={"ano": 2023},
		codigo="a" * 32,
		hash_sha256="b" * 64,
		qr_code_png=b"png",
		estado="emitido",
	)
	session.scalar.return_value = document

	result = revogar_documento(
		session,
		instituicao_id=9,
		codigo=document.codigo,
		motivo="Emissão incorreta",
	)

	assert result.estado == "revogado"
	assert result.revogado_em is not None
	assert result.motivo_revogacao == "Emissão incorreta"
	assert isinstance(result.revogado_em, datetime)
	assert result.revogado_em.tzinfo == timezone.utc
	session.commit.assert_called_once()