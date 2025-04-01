"""message-source-column

Revision ID: 961875048a2b
Revises: 515534f32c49
Create Date: 2023-11-16 18:55:01.107827+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "961875048a2b"
down_revision = "f486af9c69a8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `message`
        ADD COLUMN `source` VARCHAR(64),
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `message`
        DROP COLUMN `source`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
