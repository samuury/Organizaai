"""Cria a tabela de auditoria e impede alterações e exclusões."""

from alembic import op
import sqlalchemy as sa

revision: str = "20261120_01"
down_revision: str | None = None
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


def upgrade() -> None:
    """Cria a tabela e o trigger de imutabilidade no PostgreSQL."""
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("acao", sa.String(length=100), nullable=False),
        sa.Column("entidade", sa.String(length=100), nullable=False),
        sa.Column("entidade_id", sa.String(length=255), nullable=True),
        sa.Column("dados_antes", sa.JSON(), nullable=True),
        sa.Column("dados_depois", sa.JSON(), nullable=True),
        sa.Column(
            "ip",
            sa.String(length=45),
            nullable=True,
            comment="Endereço IPv4 ou IPv6 da origem",
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_usuario_id", "audit_log", ["usuario_id"])
    op.execute(
        """
        CREATE FUNCTION impedir_alteracao_audit_log() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log e imutavel: UPDATE e DELETE nao sao permitidos'
                USING ERRCODE = '55000';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION impedir_alteracao_audit_log()
        """
    )


def downgrade() -> None:
    """Remove o trigger, a função PostgreSQL e a tabela."""
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS impedir_alteracao_audit_log()")
    op.drop_index("ix_audit_log_usuario_id", table_name="audit_log")
    op.drop_table("audit_log")