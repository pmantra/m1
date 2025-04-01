"""client_track_add_ended_at

Revision ID: 0933f3939eb3
Revises: 42bec96e5dc5
Create Date: 2023-12-06 01:38:44.704722+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0933f3939eb3"
down_revision = "42bec96e5dc5"
branch_labels = None
depends_on = None


def upgrade():

    op.execute(
        """
        ALTER TABLE `client_track`
        ADD COLUMN `ended_at` datetime DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():

    op.execute(
        """
        ALTER TABLE `client_track`
        DROP COLUMN `ended_at`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
