"""Testes das regras de negócio da carteira digital."""

from io import BytesIO
from datetime import date

import pytest
from fastapi import HTTPException
from fastapi import Request
from sqlalchemy.dialects import postgresql

from app.modules.wallet.processing import classificar_tipo, extrair_campos
from app.modules.wallet.models import WalletDocument
from app.modules.wallet.router import get_current_user_id
from app.modules.wallet.service import (
    MAX_DOCUMENT_SIZE,
    ArquivoMuitoGrandeError,
    FormatoDocumentoInvalidoError,
    consulta_documentos,
    validar_upload,
)
from app.modules.wallet.storage import LocalStorageService
from PIL import Image


def test_upload_valida_assinatura_e_normaliza_nome() -> None:
    image_buffer = BytesIO()
    Image.new("RGB", (2, 2), color="white").save(image_buffer, format="PNG")

    result = validar_upload(r"C:\fakepath\documento.png", image_buffer.getvalue())

    assert result == ("documento.png", "image/png", ".png")


def test_upload_rejeita_arquivo_acima_de_dez_mb() -> None:
    with pytest.raises(ArquivoMuitoGrandeError):
        validar_upload("documento.pdf", b"x" * (MAX_DOCUMENT_SIZE + 1))


def test_upload_rejeita_extensao_nao_permitida() -> None:
    with pytest.raises(FormatoDocumentoInvalidoError):
        validar_upload("documento.txt", b"conteudo")


def test_storage_local_salva_le_e_remove_arquivo(tmp_path) -> None:
    storage = LocalStorageService(tmp_path)
    key = f"{'a' * 32}.pdf"

    storage.save(key, b"%PDF-1.7")
    assert storage.read(key) == b"%PDF-1.7"
    storage.delete(key)
    assert not (tmp_path / key).exists()


def test_storage_local_rejeita_chave_com_traversal(tmp_path) -> None:
    with pytest.raises(ValueError):
        LocalStorageService(tmp_path).read("../../segredo.pdf")


def test_classifica_e_extrai_campos_de_texto_ocr() -> None:
    text = (
        "DIPLOMA DE GRADUAÇÃO\n"
        "Nome: Ana Souza\n"
        "Data: 12/05/2023\n"
        "Instituição: Universidade Federal"
    )

    assert classificar_tipo(text) == "diploma"
    assert extrair_campos(text) == {
        "nome_extraido": "Ana Souza",
        "data_extraida": date(2023, 5, 12),
        "emissor_extraido": "Universidade Federal",
    }


def test_busca_compila_full_text_postgresql_e_filtra_usuario() -> None:
    statement = consulta_documentos(19, "diploma 2023")
    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "plainto_tsquery" in compiled
    assert "@@" in compiled
    assert "wallet_documents.usuario_id" in compiled
    assert "extract(year from data_extraida)" in str(
        WalletDocument.__table__.c.search_vector.computed.sqltext
    )


def test_identidade_precisa_ser_injetada_por_middleware() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/wallet/documents",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
        }
    )

    with pytest.raises(HTTPException) as error:
        get_current_user_id(request)

    assert error.value.status_code == 401