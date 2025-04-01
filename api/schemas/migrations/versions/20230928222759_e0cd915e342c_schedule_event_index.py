"""schedule_event_index

Revision ID: e0cd915e342c
Revises: d6c0ff2c2727
Create Date: 2023-09-28 22:27:59.734271+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e0cd915e342c"
down_revision = "d6c0ff2c2727"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `schedule_event`
        ADD KEY `idx_schedule_id_starts_at` (`schedule_id`, `starts_at`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
    pass


def downgrade():
    op.execute(
        """
        ALTER TABLE `schedule_event`
        DROP KEY `idx_schedule_id_starts_at`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
    pass
