"""alter excluded_procedure global_procedure_id type to string

Revision ID: ab245c928fd6
Revises: d4fdda56f76f
Create Date: 2023-08-30 12:07:58.720275+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ab245c928fd6"
down_revision = "d4fdda56f76f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_organization_settings_excluded_procedures`
        MODIFY COLUMN `global_procedure_id` VARCHAR(36) NOT NULL;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_organization_settings_excluded_procedures`
        MODIFY COLUMN `global_procedure_id` bigint(20) NOT NULL;
        """
    )
