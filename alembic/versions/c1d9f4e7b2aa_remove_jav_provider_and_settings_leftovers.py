"""remove jav provider and settings leftovers

Revision ID: c1d9f4e7b2aa
Revises: 9a6f0d7b3c21
Create Date: 2026-06-22 18:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = 'c1d9f4e7b2aa'
down_revision: Union[str, Sequence[str], None] = '9a6f0d7b3c21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_REMOVED_SETTING_KEYS = (
    'folder_adult_jav_name',
    'jav_grouping_mode',
    'folder_jav_template',
    'naming_jav_template',
)


def upgrade() -> None:
    op.execute("UPDATE metadata_matches SET media_type = 'scene' WHERE media_type = 'jav'")
    op.execute("UPDATE api_caches SET media_type = 'scene' WHERE media_type = 'jav'")
    op.execute("DELETE FROM system_settings WHERE key IN ('folder_adult_jav_name', 'jav_grouping_mode', 'folder_jav_template', 'naming_jav_template')")
    op.execute("DELETE FROM user_settings WHERE key IN ('folder_adult_jav_name', 'jav_grouping_mode', 'folder_jav_template', 'naming_jav_template')")


def downgrade() -> None:
    pass
