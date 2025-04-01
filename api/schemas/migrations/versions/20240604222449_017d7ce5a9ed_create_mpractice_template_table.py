""" create_mpractice_template_table

Revision ID: 017d7ce5a9ed
Revises: bf0c456e5cac
Create Date: 2024-06-04 22:24:49.705464+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "017d7ce5a9ed"
down_revision = "bf0c456e5cac"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        CREATE TABLE IF NOT EXISTS `mpractice_template` (
            `id` bigint(20) NOT NULL AUTO_INCREMENT comment 'Internal unique ID',
            `owner_id` int(11) NOT NULL comment 'ID column from user table (not linked)',
            `is_global` bool NOT NULL DEFAULT 0 comment 'When true, the template should be visible to all users; when false, it should only be visible to its owner',
            `title` tinytext NOT NULL comment 'A title for the template. Must be unique to this owner, or unique across all templates if is_global is true',
            `text` text NOT NULL comment 'The contents of the template',
            `sort_order` int(11) NOT NULL DEFAULT 0 comment 'User-defined sort order when retrieving templates. A smaller number is sorted before a larger number',
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP comment 'The time at which this record was created',
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP comment 'The time at which this record was updated',
            PRIMARY KEY (`id`),
            INDEX `ix_mpractice_template_is_global` (`is_global`),
            INDEX `ix_mpractice_template_owner_id` (`owner_id`)
    )
    """
    op.execute(sql)


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `mpractice_template`;
        """
    )
