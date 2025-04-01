"""add-auto-increment-per-procedure-table

Revision ID: 4ac3db519080
Revises: 66140deb4e7f
Create Date: 2023-11-30 17:12:03.273702+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "4ac3db519080"
down_revision = "66140deb4e7f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_organization_settings_require_procedures`
            RENAME TO `reimbursement_organization_settings_dx_required_procedures`,
            MODIFY `id` BIGINT AUTO_INCREMENT,
            ADD CONSTRAINT uq_organization_settings_dx_required_procedure UNIQUE (
                reimbursement_org_settings_id, global_procedure_id
            );
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_organization_settings_dx_required_procedures`
            RENAME TO `reimbursement_organization_settings_require_procedures`,
            MODIFY `id` BIGINT,
            DROP KEY uq_organization_settings_dx_required_procedure;
        """
    )
