"""create incentive-organization table

Revision ID: a6443b73f945
Revises: e98268b6c54c
Create Date: 2023-10-11 16:23:58.734717+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a6443b73f945"
down_revision = "e98268b6c54c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `incentive_organization` (
            `id` bigint(20) PRIMARY KEY NOT NULL AUTO_INCREMENT,
            `organization_id` bigint(20) NOT NULL,
            `incentive_id` int(11) NOT NULL,
            `action` enum('CA_INTRO', 'OFFBOARDING_ASSESSMENT') NOT NULL,
            `track_name` VARCHAR(120) NOT NULL,
            `active` bool NOT NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            KEY (organization_id),
            FOREIGN KEY (incentive_id)
                REFERENCES `incentive`(`id`)
                ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS `incentive_organization_country` (
            `id` bigint(20) PRIMARY KEY NOT NULL AUTO_INCREMENT,
            `incentive_organization_id` bigint(20) NOT NULL,
            `country_code` VARCHAR(2) NOT NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (incentive_organization_id)
                REFERENCES `incentive_organization`(`id`)
                ON DELETE CASCADE,
            UNIQUE (`incentive_organization_id`, `country_code`)
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `incentive_organization_country`;
        DROP TABLE IF EXISTS `incentive_organization`;
        """
    )
