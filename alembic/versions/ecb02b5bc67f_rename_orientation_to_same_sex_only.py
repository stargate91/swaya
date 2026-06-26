"""rename_orientation_to_same_sex_only

Revision ID: ecb02b5bc67f
Revises: 162b364cfe05
Create Date: 2026-06-27 00:59:28.970968

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ecb02b5bc67f'
down_revision: Union[str, Sequence[str], None] = '162b364cfe05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_people_orientation")
    op.execute("ALTER TABLE people RENAME COLUMN orientation TO same_sex_only")
    op.execute("CREATE INDEX ix_people_same_sex_only ON people (same_sex_only)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_people_same_sex_only")
    op.execute("ALTER TABLE people RENAME COLUMN same_sex_only TO orientation")
    op.execute("CREATE INDEX ix_people_orientation ON people (orientation)")
