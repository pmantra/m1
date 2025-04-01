"""Add discount rate to fertility clinic

Revision ID: cafebb1294bb
Revises: 24806fa6615d
Create Date: 2024-01-18 21:06:01.763210+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "cafebb1294bb"
down_revision = "24806fa6615d"
branch_labels = None
depends_on = None


def upgrade():
    query = """
        CREATE TABLE `fertility_clinic_location_contact` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
            `fertility_clinic_location_id` bigint(20) NOT NULL,
            `name` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `phone_number` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_fertility_clinic_location_id` (`fertility_clinic_location_id`),
            CONSTRAINT `fertility_clinic_location_contact_ibfk_1` FOREIGN KEY (`fertility_clinic_location_id`) REFERENCES `fertility_clinic_location` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    op.execute(query)


def downgrade():
    query = "DROP TABLE IF EXISTS `fertility_clinic_location_contact`;"
    op.execute(query)
