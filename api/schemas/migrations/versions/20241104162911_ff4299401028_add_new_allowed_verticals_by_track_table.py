"""add_new_allowed_verticals_by_track_table

Revision ID: ff4299401028
Revises: 5b6af8f0f8cb
Create Date: 2024-11-04 16:29:11.454440+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "ff4299401028"
down_revision = "0112b9863aee"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE `vertical_access_by_track` (
        `client_track_id` INT NOT NULL,
        `vertical_id` INT NOT NULL,
        `track_modifiers` TEXT DEFAULT NULL,
        `created_at` datetime DEFAULT NULL,
        `modified_at` datetime DEFAULT NULL,
        PRIMARY KEY (`client_track_id`, `vertical_id`),
        FOREIGN KEY (`vertical_id`) REFERENCES `vertical` (`id`) ON DELETE CASCADE)
        ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE `vertical_access_by_track`;
        """
    )
