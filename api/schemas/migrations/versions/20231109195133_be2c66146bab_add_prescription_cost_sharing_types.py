"""add_prescription_cost_sharing_types

Revision ID: be2c66146bab
Revises: b8160d62dd2f
Create Date: 2023-11-09 19:51:33.611260+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "be2c66146bab"
down_revision = "b8160d62dd2f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan_cost_sharing`
        CHANGE COLUMN `cost_sharing_category` `cost_sharing_category` enum('CONSULTATION','MEDICAL_CARE','DIAGNOSTIC_MEDICAL', 'GENERIC_PRESCRIPTIONS', 'SPECIATY_PRESCRIPTIONS') NOT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan_cost_sharing`
        CHANGE COLUMN `cost_sharing_category` `cost_sharing_category` enum('CONSULTATION','MEDICAL_CARE','DIAGNOSTIC_MEDICAL') NOT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
