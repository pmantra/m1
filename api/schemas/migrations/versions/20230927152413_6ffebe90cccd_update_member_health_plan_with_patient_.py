"""update member_health_plan with patient info

Revision ID: 6ffebe90cccd
Revises: e501d62a6d76
Create Date: 2023-09-27 15:24:13.984039+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "6ffebe90cccd"
down_revision = "b48e1b700e6a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan`
        ADD COLUMN `patient_first_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ADD COLUMN `patient_last_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ADD COLUMN `patient_date_of_birth` date DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan`
        DROP COLUMN `patient_first_name`,
        DROP COLUMN `patient_last_name`,
        DROP COLUMN `patient_date_of_birth`,
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )
