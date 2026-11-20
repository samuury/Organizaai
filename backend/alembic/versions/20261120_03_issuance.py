"""Cria lotes e documentos emitidos pelas instituições."""

from alembic import op
import sqlalchemy as sa

revision: str = "20261120_03"
down_revision: str | None = "20261120_02"
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


def upgrade() -> None:
    """Cria tabelas e índices do fluxo de emissão."""
    op.create_table(
        "issuance_batches",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("instituicao_id", sa.Integer(), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=24),
            server_default="pendente",
            nullable=False,
        ),
        sa.Column("total_linhas", sa.Integer(), nullable=False),
        sa.Column("validas", sa.Integer(), nullable=False),
        sa.Column("erros_validacao", sa.JSON(), nullable=False),
        sa.Column("erros_processamento", sa.JSON(), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("finalizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado IN ('pendente', 'processando', 'concluido', 'concluido_com_erros')",
            name="ck_issuance_batches_estado",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_issuance_batches_instituicao_criado",
        "issuance_batches",
        ["instituicao_id", "criado_em"],
    )
    op.create_table(
        "issued_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instituicao_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("lote_id", sa.String(length=32), nullable=True),
        sa.Column("linha_lote", sa.Integer(), nullable=True),
        sa.Column("titulo", sa.String(length=255), nullable=False),
        sa.Column("tipo_documento", sa.String(length=20), nullable=False),
        sa.Column("conteudo", sa.JSON(), nullable=False),
        sa.Column("codigo", sa.String(length=32), nullable=False),
        sa.Column("hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("qr_code_png", sa.LargeBinary(), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=12),
            server_default="emitido",
            nullable=False,
        ),
        sa.Column("motivo_revogacao", sa.Text(), nullable=True),
        sa.Column(
            "emitido_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("revogado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "tipo_documento IN ('diploma', 'certidao', 'comprovante')",
            name="ck_issued_documents_tipo",
        ),
        sa.CheckConstraint(
            "estado IN ('emitido', 'revogado')",
            name="ck_issued_documents_estado",
        ),
        sa.CheckConstraint("length(hash_sha256) = 64", name="ck_issued_documents_hash"),
        sa.ForeignKeyConstraint(
            ["lote_id"], ["issuance_batches.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_issued_documents_codigo", "issued_documents", ["codigo"], unique=True
    )
    op.create_index(
        "ix_issued_documents_instituicao", "issued_documents", ["instituicao_id"]
    )
    op.create_index("ix_issued_documents_usuario", "issued_documents", ["usuario_id"])
    op.create_index(
        "ix_issued_documents_lote_linha",
        "issued_documents",
        ["lote_id", "linha_lote"],
    )


def downgrade() -> None:
    """Remove documentos, lotes e índices de emissão."""
    op.drop_index("ix_issued_documents_lote_linha", table_name="issued_documents")
    op.drop_index("ix_issued_documents_usuario", table_name="issued_documents")
    op.drop_index("ix_issued_documents_instituicao", table_name="issued_documents")
    op.drop_index("ix_issued_documents_codigo", table_name="issued_documents")
    op.drop_table("issued_documents")
    op.drop_index(
        "ix_issuance_batches_instituicao_criado", table_name="issuance_batches"
    )
    op.drop_table("issuance_batches")