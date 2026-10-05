"""add timestamps to chat_sessions

Revision ID: add_chat_sessions_timestamps
Revises: 247425fdaa50
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_chat_sessions_timestamps'
down_revision: Union[str, Sequence[str], None] = '247425fdaa50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add created_at and updated_at columns."""
    op.add_column('chat_sessions', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.add_column('chat_sessions', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    """Downgrade schema - remove created_at and updated_at columns."""
    op.drop_column('chat_sessions', 'updated_at')
    op.drop_column('chat_sessions', 'created_at')
