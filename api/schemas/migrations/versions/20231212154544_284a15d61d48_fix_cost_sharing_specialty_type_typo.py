"""fix_cost_sharing_specialty_type_typo

Revision ID: 284a15d61d48
Revises: e68ad96bbc45
Create Date: 2023-12-12 15:45:44.953973+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "284a15d61d48"
down_revision = "e68ad96bbc45"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan_cost_sharing`
        CHANGE COLUMN `cost_sharing_category` `cost_sharing_category` enum('CONSULTATION','MEDICAL_CARE','DIAGNOSTIC_MEDICAL', 'GENERIC_PRESCRIPTIONS', 'SPECIALTY_PRESCRIPTIONS') NOT NULL;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan_cost_sharing`
        CHANGE COLUMN `cost_sharing_category` `cost_sharing_category` enum('CONSULTATION','MEDICAL_CARE','DIAGNOSTIC_MEDICAL', 'GENERIC_PRESCRIPTIONS', 'SPECIATY_PRESCRIPTIONS') NOT NULL;
        """
    )
