"""Adiciona índices para métricas temporais do dashboard."""

from alembic import op

revision: str = "20261120_06"
down_revision: str | None = "20261120_05"
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


def upgrade() -> None:
	"""Cria índices para agregações de atividade recentes."""
	op.create_index("ix_audit_log_acao_criado", "audit_log", ["acao", "criado_em"])
	op.create_index(
		"ix_audit_log_criado_usuario", "audit_log", ["criado_em", "usuario_id"]
	)
	op.create_index(
		"ix_issued_documents_emitido_em", "issued_documents", ["emitido_em"]
	)


def downgrade() -> None:
	"""Remove os índices temporais do dashboard."""
	op.drop_index("ix_issued_documents_emitido_em", table_name="issued_documents")
	op.drop_index("ix_audit_log_criado_usuario", table_name="audit_log")
	op.drop_index("ix_audit_log_acao_criado", table_name="audit_log")