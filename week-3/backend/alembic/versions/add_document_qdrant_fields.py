"""Add session_id, ingestion_status, ingestion_error, created_at to documents table.

Revision ID: add_document_qdrant_fields
Revises: add_chat_sessions_timestamps
Create Date: 2026-09-28 08:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_document_qdrant_fields'
down_revision: Union[str, Sequence[str], None] = 'add_chat_sessions_timestamps'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Extend the documents table with:
    - session_id         FK → chat_sessions.id  (multi-tenant scoping)
    - ingestion_status   VARCHAR(20), default 'pending'
    - ingestion_error    TEXT, nullable (stores error message on failure)
    - created_at         TIMESTAMPTZ, server default now()
    """
    # Add session_id FK column (nullable at first to allow backfilling on existing rows)
    op.add_column(
        'documents',
        sa.Column('session_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_documents_session_id',
        'documents',
        'chat_sessions',
        ['session_id'],
        ['id'],
    )

    # Add ingestion lifecycle columns
    op.add_column(
        'documents',
        sa.Column(
            'ingestion_status',
            sa.String(20),
            nullable=False,
            server_default='pending',
        ),
    )
    op.add_column(
        'documents',
        sa.Column('ingestion_error', sa.Text(), nullable=True),
    )

    # Add created_at timestamp
    op.add_column(
        'documents',
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove the columns added in upgrade()."""
    op.drop_column('documents', 'created_at')
    op.drop_column('documents', 'ingestion_error')
    op.drop_column('documents', 'ingestion_status')
    op.drop_constraint('fk_documents_session_id', 'documents', type_='foreignkey')
    op.drop_column('documents', 'session_id')
