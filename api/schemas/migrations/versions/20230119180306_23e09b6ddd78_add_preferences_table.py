"""add_preferences_table

Revision ID: 23e09b6ddd78
Revises: 29a2df1743fe
Create Date: 2023-01-19 18:03:06.766172+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "23e09b6ddd78"
down_revision = "29a2df1743fe"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
            CREATE TABLE IF NOT EXISTS `preferences` (
                `id` INT(11) PRIMARY KEY NOT NULL AUTO_INCREMENT,
                `name` VARCHAR(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                `default_value` VARCHAR(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                `type` VARCHAR(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL
        )
            """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS `preferences`;")
