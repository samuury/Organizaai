"""Cria os documentos da carteira e o índice full-text."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261120_02"
down_revision: str | None = "20261120_01"
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None

_SEARCH_VECTOR_EXPRESSION = """
setweight(to_tsvector('portuguese', coalesce(nome_arquivo, '')), 'D') ||
setweight(to_tsvector('portuguese', coalesce(tipo_documento, '')), 'A') ||
setweight(to_tsvector('portuguese', coalesce(nome_extraido, '')), 'A') ||
setweight(to_tsvector('portuguese', coalesce(emissor_extraido, '')), 'B') ||
setweight(to_tsvector('simple', coalesce(extract(year from data_extraida)::text, '')), 'B') ||
setweight(to_tsvector('portuguese', coalesce(texto_ocr, '')), 'C')
"""


def upgrade() -> None:
    """Cria os metadados da carteira e o índice GIN do vetor de busca."""
    op.create_table(
        "wallet_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("nome_arquivo", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("tamanho_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "estado_processamento",
            sa.String(length=20),
            server_default="pendente",
            nullable=False,
        ),
        sa.Column("tipo_documento", sa.String(length=20), nullable=True),
        sa.Column("nome_extraido", sa.String(length=255), nullable=True),
        sa.Column("data_extraida", sa.Date(), nullable=True),
        sa.Column("emissor_extraido", sa.String(length=255), nullable=True),
        sa.Column("texto_ocr", sa.Text(), nullable=True),
        sa.Column("erro_processamento", sa.String(length=255), nullable=True),
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
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(_SEARCH_VECTOR_EXPRESSION, persisted=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tamanho_bytes > 0 AND tamanho_bytes <= 10485760",
            name="ck_wallet_documents_tamanho",
        ),
        sa.CheckConstraint(
            "tipo_documento IS NULL OR tipo_documento IN "
            "('diploma', 'certidao', 'comprovante')",
            name="ck_wallet_documents_tipo",
        ),
        sa.CheckConstraint(
            "estado_processamento IN ('pendente', 'processando', 'concluido', 'falhou')",
            name="ck_wallet_documents_estado",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        "ix_wallet_documents_usuario_criado",
        "wallet_documents",
        ["usuario_id", "criado_em"],
    )
    op.create_index(
        "ix_wallet_documents_search_vector",
        "wallet_documents",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Remove os índices e a tabela da carteira."""
    op.drop_index("ix_wallet_documents_search_vector", table_name="wallet_documents")
    op.drop_index("ix_wallet_documents_usuario_criado", table_name="wallet_documents")
    op.drop_table("wallet_documents")