"""add_created_at_and_modified_at_to_preferences_tables

Revision ID: 8e05adaeed11
Revises: 6260fdd23e87
Create Date: 2023-01-25 14:13:05.680001+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "8e05adaeed11"
down_revision = "6260fdd23e87"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("RENAME TABLE `preferences` TO `preference`;")
    op.execute(
        """
        ALTER TABLE `preference`
        ADD COLUMN `created_at` DATETIME DEFAULT NULL,
        ADD COLUMN `modified_at` DATETIME DEFAULT NULL;
        """
    )

    op.execute(
        """
        ALTER TABLE `member_preferences`
        ADD COLUMN `created_at` DATETIME DEFAULT NULL,
        ADD COLUMN `modified_at` DATETIME DEFAULT NULL;
        """
    )


def downgrade():
    op.execute("RENAME TABLE `preference` TO `preferences`;")
    op.execute(
        """
        ALTER TABLE `preferences`
        DROP COLUMN `created_at`,
        DROP COLUMN `modified_at`;
        """
    )
    op.execute(
        """
        ALTER TABLE `member_preferences`
        DROP COLUMN `created_at`,
        DROP COLUMN `modified_at`;
        """
    )
