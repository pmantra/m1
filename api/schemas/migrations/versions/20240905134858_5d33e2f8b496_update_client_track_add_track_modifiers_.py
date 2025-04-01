"""update_client_track_add_track_modifiers_column

Revision ID: 5d33e2f8b496
Revises: 65fb78b5c034
Create Date: 2024-09-05 13:48:58.857135+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "5d33e2f8b496"
down_revision = "65fb78b5c034"
branch_labels = None
depends_on = None


def upgrade():

    # add the `track_modifiers` column as `text` in order to hold comma separated values (the values here will be enum)
    op.execute(
        """
        ALTER TABLE `client_track`
        ADD COLUMN `track_modifiers` text DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `client_track`
        DROP COLUMN `track_modifiers`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
