"""add slug for l10n ca_member_transition_template

Revision ID: 0bfca93d4c21
Revises: d81769b17be7
Create Date: 2024-09-03 17:15:24.111472+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0bfca93d4c21"
down_revision = "d81769b17be7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `ca_member_transition_template`
        ADD COLUMN `slug` VARCHAR(128) DEFAULT NULL,
        ADD UNIQUE KEY `slug_uq_1` (`slug`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `ca_member_transition_template`
        DROP COLUMN `slug`,
        DROP KEY `slug_uq_1`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
