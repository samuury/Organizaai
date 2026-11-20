"""Armazena o nome do emissor no momento da emissão."""

from alembic import op
import sqlalchemy as sa

revision: str = "20261120_04"
down_revision: str | None = "20261120_03"
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


def upgrade() -> None:
	"""Adiciona o snapshot do nome institucional a lotes e documentos."""
	op.add_column(
		"issuance_batches",
		sa.Column(
			"emissor",
			sa.String(length=255),
			server_default="Instituição",
			nullable=False,
		),
	)
	op.add_column(
		"issued_documents",
		sa.Column(
			"emissor",
			sa.String(length=255),
			server_default="Instituição",
			nullable=False,
		),
	)


def downgrade() -> None:
	"""Remove os snapshots de emissor."""
	op.drop_column("issued_documents", "emissor")
	op.drop_column("issuance_batches", "emissor")