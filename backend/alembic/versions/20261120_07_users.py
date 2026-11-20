"""Cria tabela de usuários e perfis de acesso."""

from alembic import op
import sqlalchemy as sa

revision: str = "20261120_07"
down_revision: str | None = "20261120_06"
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


def upgrade() -> None:
	"""Cria tabela de usuários, restrição de perfil e índice por e-mail."""
	op.create_table(
		"users",
		sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
		sa.Column("nome", sa.String(length=255), nullable=False),
		sa.Column("email", sa.String(length=255), nullable=False),
		sa.Column("senha_hash", sa.String(length=255), nullable=False),
		sa.Column("perfil", sa.String(length=20), nullable=False),
		sa.Column(
			"criado_em",
			sa.DateTime(timezone=True),
			server_default=sa.text("CURRENT_TIMESTAMP"),
			nullable=False,
		),
		sa.Column(
			"atualizado_em",
			sa.DateTime(timezone=True),
			server_default=sa.text("CURRENT_TIMESTAMP"),
			nullable=False,
		),
		sa.CheckConstraint(
			"perfil IN ('CIDADAO', 'INSTITUICAO', 'EMPRESA')",
			name="ck_users_perfil",
		),
		sa.PrimaryKeyConstraint("id"),
	)
	op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
	"""Remove a tabela de usuários."""
	op.drop_index("ix_users_email", table_name="users")
	op.drop_table("users")
