"""reimbursement-request-cost-breakdown-calculation-fields

Revision ID: eb151dc505e4
Revises: 569c4492e421
Create Date: 2024-02-06 00:05:35.464976+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "eb151dc505e4"
down_revision = "569c4492e421"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_request`
        ADD COLUMN `cost_sharing_category` enum('CONSULTATION','MEDICAL_CARE','DIAGNOSTIC_MEDICAL','GENERIC_PRESCRIPTIONS','SPECIALTY_PRESCRIPTIONS') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ADD COLUMN `procedure_type` enum('MEDICAL','PHARMACY') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_request`
        DROP COLUMN `cost_sharing_category`,
        DROP COLUMN `procedure_type`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
