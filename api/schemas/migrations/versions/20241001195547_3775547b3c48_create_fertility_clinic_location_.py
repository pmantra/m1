"""create_fertility_clinic_location_employer_health_plan_tier

Revision ID: 3775547b3c48
Revises: 480564170330
Create Date: 2024-10-01 19:55:47.913326+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3775547b3c48"
down_revision = "480564170330"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `fertility_clinic_location_employer_health_plan_tier` (
            `id` bigint(20) primary key NOT NULL AUTO_INCREMENT,
            `fertility_clinic_location_id` bigint(20) NOT NULL,
            `employer_health_plan_id` bigint(20) NOT NULL,
            `start_date` date DEFAULT NULL,
            `end_date` date DEFAULT NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            CONSTRAINT `fertility_clinic_location_employer_health_plan_tier_ibfk_1` FOREIGN KEY (`fertility_clinic_location_id`) REFERENCES `fertility_clinic_location` (`id`),
            CONSTRAINT `fertility_clinic_location_employer_health_plan_tier_ibfk_2` FOREIGN KEY (`employer_health_plan_id`) REFERENCES `employer_health_plan` (`id`)
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `fertility_clinic_location_employer_health_plan_tier`;
        """
    )
