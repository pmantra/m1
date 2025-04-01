"""PAY-4763-add-member-id

Revision ID: e98268b6c54c
Revises: e0cd915e342c
Create Date: 2023-10-09 20:04:54.218585+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "e98268b6c54c"
down_revision = "e0cd915e342c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan`
        ADD COLUMN member_id int(11) DEFAULT NULL,
        ADD INDEX member_id (member_id),
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan`
        DROP COLUMN member_id,
        DROP INDEX member_id,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
