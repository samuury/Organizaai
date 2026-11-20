"""Testes do registro de auditoria."""

from unittest.mock import Mock

from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from app.modules.audit.service import registrar_auditoria


def test_registrar_auditoria_adiciona_evento_sem_confirmar_transacao() -> None:
    session = Mock(spec=Session)

    registro = registrar_auditoria(
        session,
        usuario_id=17,
        acao="documento.atualizado",
        entidade="documento",
        entidade_id=42,
        dados_antes={"nome": "antigo"},
        dados_depois={"nome": "novo"},
        ip="192.0.2.10",
    )

    assert isinstance(registro, AuditLog)
    assert registro.usuario_id == 17
    assert registro.acao == "documento.atualizado"
    assert registro.entidade == "documento"
    assert registro.entidade_id == "42"
    assert registro.dados_antes == {"nome": "antigo"}
    assert registro.dados_depois == {"nome": "novo"}
    assert registro.ip == "192.0.2.10"
    session.add.assert_called_once_with(registro)
    session.commit.assert_not_called()