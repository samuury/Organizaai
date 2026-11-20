"""Cria concessões temporárias de acesso a documentos."""

from alembic import op
import sqlalchemy as sa

revision: str = "20261120_05"
down_revision: str | None = "20261120_04"
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


def upgrade() -> None:
	"""Cria tabela e índices para concessão, expiração e revogação."""
	op.create_table(
		"document_consents",
		sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
		sa.Column("documento_id", sa.Integer(), nullable=False),
		sa.Column("cidadao_id", sa.Integer(), nullable=False),
		sa.Column("empresa_id", sa.Integer(), nullable=False),
		sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
		sa.Column("revogado_em", sa.DateTime(timezone=True), nullable=True),
		sa.Column(
			"criado_em",
			sa.DateTime(timezone=True),
			server_default=sa.text("CURRENT_TIMESTAMP"),
			nullable=False,
		),
		sa.CheckConstraint("empresa_id > 0", name="ck_document_consents_empresa_id"),
		sa.ForeignKeyConstraint(
			["documento_id"], ["wallet_documents.id"], ondelete="CASCADE"
		),
		sa.PrimaryKeyConstraint("id"),
	)
	op.create_index(
		"ix_document_consents_document_company_expiry",
		"document_consents",
		["documento_id", "empresa_id", "expira_em"],
	)
	op.create_index(
		"ix_document_consents_owner_expiry",
		"document_consents",
		["cidadao_id", "expira_em"],
	)


def downgrade() -> None:
	"""Remove os índices e a tabela de consentimentos."""
	op.drop_index(
		"ix_document_consents_owner_expiry", table_name="document_consents"
	)
	op.drop_index(
		"ix_document_consents_document_company_expiry", table_name="document_consents"
	)
	op.drop_table("document_consents")