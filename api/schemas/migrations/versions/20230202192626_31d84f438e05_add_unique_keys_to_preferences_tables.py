"""add_unique_keys_to_preferences_tables

Revision ID: 31d84f438e05
Revises: 72211219bc7a
Create Date: 2023-02-02 19:26:26.325549+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "31d84f438e05"
down_revision = "72211219bc7a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_preferences` ADD UNIQUE `uq_member_preference`(`member_id`, `preference_id`)
        """
    )

    op.execute(
        """
        ALTER TABLE `preference` 
        MODIFY COLUMN `name` VARCHAR(120) NOT NULL,
        ADD UNIQUE `uq_preference_name` (`name`);
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_preferences` DROP INDEX `uq_member_preference`
        """
    )

    op.execute(
        """
        ALTER TABLE `preference` 
        DROP INDEX `uq_preference_name`,
        MODIFY COLUMN `name` VARCHAR(255) NOT NULL;
        """
    )
