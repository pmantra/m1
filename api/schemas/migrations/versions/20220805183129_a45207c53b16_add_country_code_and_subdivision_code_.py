"""Add country_code and subdivision_code to MemberProfile and PractitionerProfile tables

Revision ID: a45207c53b16
Revises: d0a66cb30d3e
Create Date: 2022-08-05 18:31:29.171785+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a45207c53b16"
down_revision = "d0a66cb30d3e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_profile` 
        ADD COLUMN `first_name` VARCHAR(40) DEFAULT NULL,
        ADD COLUMN `middle_name` VARCHAR(40) DEFAULT NULL,
        ADD COLUMN `last_name` VARCHAR(40) DEFAULT NULL,
        ADD COLUMN `username` VARCHAR(100) DEFAULT NULL,
        ADD COLUMN `zendesk_user_id` bigint(20) DEFAULT NULL,
        ADD COLUMN `timezone` VARCHAR(128) NOT NULL DEFAULT 'UTC',
        ADD COLUMN `country_code` VARCHAR(2),
        ADD COLUMN `subdivision_code` VARCHAR(6),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )

    op.execute(
        """
        ALTER TABLE `practitioner_profile` 
        ADD COLUMN `first_name` VARCHAR(40) DEFAULT NULL,
        ADD COLUMN `middle_name` VARCHAR(40) DEFAULT NULL,
        ADD COLUMN `last_name` VARCHAR(40) DEFAULT NULL,
        ADD COLUMN `username` VARCHAR(100) DEFAULT NULL,
        ADD COLUMN `zendesk_user_id` bigint(20) DEFAULT NULL,
        ADD COLUMN `timezone` VARCHAR(128) NOT NULL DEFAULT 'UTC',
        ADD COLUMN `country_code` VARCHAR(2),
        ADD COLUMN `subdivision_code` VARCHAR(6),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_profile`
        DROP COLUMN `first_name`,
        DROP COLUMN `middle_name`,
        DROP COLUMN `last_name`,
        DROP COLUMN `username`,
        DROP COLUMN `zendesk_user_id`,
        DROP COLUMN `timezone`,
        DROP COLUMN `country_code`,
        DROP COLUMN `subdivision_code`;
        """
    )

    op.execute(
        """
        ALTER TABLE `practitioner_profile`
        DROP COLUMN `first_name`,
        DROP COLUMN `middle_name`,
        DROP COLUMN `last_name`,
        DROP COLUMN `username`,
        DROP COLUMN `zendesk_user_id`,
        DROP COLUMN `timezone`,
        DROP COLUMN `country_code`,
        DROP COLUMN `subdivision_code`;
        """
    )
