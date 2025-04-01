"""add_backfill_verification_state_table

Revision ID: 0e04afa08f7c
Revises: 929f151dda70
Create Date: 2023-08-07 14:16:59.213449+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0e04afa08f7c"
down_revision = "7af0929bffae"
branch_labels = None
depends_on = None


def upgrade():
    # the `backfill_verification_state` contains PII in the following columns
    # first_name, last_name, date_of_birth, email
    # It will be populdated in next MR(https://gitlab.com/maven-clinic/maven/maven/-/merge_requests/6855)
    # The whole table is a temp table only for backfill purpose,
    # The table will be dropped after backfill (https://gitlab.com/maven-clinic/maven/maven/-/merge_requests/6874)
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS maven.`backfill_verification_state` (
      `id` int(11) NOT NULL AUTO_INCREMENT,
      `user_organization_employee_id` int(11) NOT NULL,
      `organization_employee_id` int(11) NOT NULL,
      `user_id` int(11) NOT NULL,
      `organization_id` int(11) NOT NULL,
      `eligibility_member_id` int(11) DEFAULT NULL,
      `verification_type` enum('STANDARD','ALTERNATE','FILELESS','CLIENT_SPECIFIC','SAML','HEALTHPLAN','UNKNOWN') COLLATE utf8mb4_unicode_ci DEFAULT NULL, -- from organization.eligibility_type
      `unique_corp_id` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `dependent_id` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
      `first_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `last_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `date_of_birth` date NOT NULL,
      `email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `work_state` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `verified_at` datetime DEFAULT NULL, -- from organization_employee.created_at
      `deactivated_at` datetime DEFAULT NULL, -- from organization_employee.deleted_at
      `backfill_verification_id` int(11) DEFAULT NULL,
      `backfill_error` text COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      PRIMARY KEY (`id`),
      KEY `user_organization_employee_id` (`user_organization_employee_id`),
      KEY `organization_employee_id` (`organization_employee_id`),
      KEY `user_id` (`user_id`),
      KEY `organization_id` (`organization_id`)
    ) ENGINE=InnoDB;
    """
    )


def downgrade():
    op.execute(
        """
    DROP TABLE IF EXISTS maven.`backfill_verification_state`;
    """
    )
