"""

Revision ID: 177bd932f17d
Revises: 615117589a9a
Create Date: 2024-11-12 18:33:44.991162+00:00

"""
from alembic import op
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = "177bd932f17d"
down_revision = "615117589a9a"
branch_labels = None
depends_on = None

fixed_timestamp = "2024-01-01 00:00:00"


def upgrade():
    op.execute(
        text(
            f"""
            UPDATE user_locale_preference
            SET
                created_at = COALESCE(created_at, '{fixed_timestamp}'),
                modified_at = COALESCE(modified_at, '{fixed_timestamp}')
            WHERE
                created_at IS NULL OR modified_at IS NULL;
            """
        )
    )


def downgrade():
    op.execute(
        text(
            f"""
            UPDATE user_locale_preference
            SET created_at = NULL
            WHERE created_at = '{fixed_timestamp}';

            UPDATE user_locale_preference
            SET
                modified_at = NULL
            WHERE modified_at = '{fixed_timestamp}';
            """
        )
    )
