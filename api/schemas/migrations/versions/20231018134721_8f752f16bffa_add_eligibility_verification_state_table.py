"""Add eligibility verification state table

Revision ID: 8f752f16bffa
Revises: 30c547014222
Create Date: 2023-10-18 13:47:21.610229+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "8f752f16bffa"
down_revision = "d2c71cd58430"
branch_labels = None
depends_on = None


def upgrade():
    # the `eligibility_verification_state` contains PII in the following columns
    # first_name, last_name, date_of_birth, email
    # The whole table is a temp table only for backfill/validation purpose,
    # The table will be dropped after backfill
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS maven.`eligibility_verification_state` (
      `id` int(11) NOT NULL AUTO_INCREMENT,
      -- fields populated from mono data
      `user_id` int(11) NOT NULL,
      `user_organization_employee_id` int(11) NOT NULL,
      `organization_employee_id` int(11) NOT NULL,
      `organization_id` int(11) NOT NULL,
      `oe_member_id` int(11) DEFAULT NULL,
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
      -- validation fields from e9y data
      `e9y_member_id` int(11) DEFAULT NULL,
      `e9y_verification_id` int(11) DEFAULT NULL,
      `e9y_organization_id` int(11) DEFAULT NULL,
      `e9y_unique_corp_id` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `e9y_dependent_id` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
      `backfill_status` text COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      PRIMARY KEY (`id`),
      CONSTRAINT unique_user_id UNIQUE (`user_id`),
      CONSTRAINT `user_organization_employee_id_ibfk1` FOREIGN KEY (`user_organization_employee_id`) REFERENCES `user_organization_employee` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
      CONSTRAINT `organization_employee_id_ibfk1` FOREIGN KEY (`organization_employee_id`) REFERENCES `organization_employee` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
      CONSTRAINT `user_id_ibfk1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
      CONSTRAINT `organization_id_ibfk1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
    ) ENGINE=InnoDB;
    """
    )


def downgrade():
    op.execute(
        """
    DROP TABLE IF EXISTS maven.`eligibility_verification_state`;
    """
    )
