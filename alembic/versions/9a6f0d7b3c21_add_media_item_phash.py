"""add media item phash

Revision ID: 9a6f0d7b3c21
Revises: ba8eae085467
Create Date: 2026-06-22 16:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9a6f0d7b3c21'
down_revision: Union[str, Sequence[str], None] = '851f9ea1a4e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('media_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hash_phash', sa.String(), nullable=True))
        batch_op.create_index(batch_op.f('ix_media_items_hash_phash'), ['hash_phash'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('media_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_media_items_hash_phash'))
        batch_op.drop_column('hash_phash')
