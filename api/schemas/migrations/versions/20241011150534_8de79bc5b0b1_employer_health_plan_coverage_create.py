"""employer_health_plan_coverage_create

Revision ID: 8de79bc5b0b1
Revises: a3abe83fc80e
Create Date: 2024-10-11 15:05:34.618085+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "8de79bc5b0b1"
down_revision = "a3abe83fc80e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `employer_health_plan_coverage` (
            `id` bigint(20) primary key NOT NULL AUTO_INCREMENT,
            `employer_health_plan_id` bigint(20) NOT NULL,
            `individual_deductible` int(11) DEFAULT NULL,
            `individual_oop` int(11) DEFAULT NULL,
            `family_deductible` int(11) DEFAULT NULL,
            `family_oop` int(11) DEFAULT NULL,
            `max_oop_per_covered_individual` int(11) DEFAULT NULL,
            `is_deductible_embedded` tinyint(1) NOT NULL DEFAULT '0',
            `is_oop_embedded` tinyint(1) NOT NULL DEFAULT '0',
            `plan_type` varchar(255) NOT NULL,
            `coverage_type` ENUM('RX', 'MEDICAL') NOT NULL,
            `tier` smallint DEFAULT NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            CONSTRAINT `employer_health_plan_coverage_ibfk_1` FOREIGN KEY (`employer_health_plan_id`) REFERENCES `employer_health_plan` (`id`) ON DELETE CASCADE
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `employer_health_plan_coverage`;
        """
    )
