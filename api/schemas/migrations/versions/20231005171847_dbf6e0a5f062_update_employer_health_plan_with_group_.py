"""update employer_health_plan with group_id

Revision ID: dbf6e0a5f062
Revises: 950b5e0caee4
Create Date: 2023-10-05 17:18:47.787513+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "dbf6e0a5f062"
down_revision = "77869680cc2c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """  
        CREATE TABLE `employer_health_plan_group_id` (
          `employer_health_plan_id` bigint(20) NOT NULL,
          `employer_group_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
          PRIMARY KEY (`employer_health_plan_id`, `employer_group_id`),
          CONSTRAINT `employer_health_plan_group_id_ibfk_1` FOREIGN KEY (`employer_health_plan_id`) REFERENCES `employer_health_plan` (`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE `employer_health_plan_group_id`;
        """
    )
