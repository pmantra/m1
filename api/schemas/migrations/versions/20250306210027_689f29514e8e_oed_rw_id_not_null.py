"""oed_rw_id_not_null

Revision ID: 689f29514e8e
Revises: a00d71b4947f
Create Date: 2025-03-06 21:00:27.356571+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "689f29514e8e"
down_revision = "a00d71b4947f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    ALTER TABLE `organization_employee_dependent`
    DROP FOREIGN KEY `organization_employee_dependent__reimbursement_wallet_fk`;
    """
    )

    op.execute(
        """
    ALTER TABLE `organization_employee_dependent`
    MODIFY COLUMN `reimbursement_wallet_id` bigint(20) NOT NULL;
    """
    )

    op.execute(
        """
    ALTER TABLE `organization_employee_dependent`
    ADD CONSTRAINT `organization_employee_dependent__reimbursement_wallet_fk` 
    FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`) 
    ON DELETE CASCADE ON UPDATE CASCADE;
    """
    )


def downgrade():
    op.execute(
        """
    ALTER TABLE `organization_employee_dependent`
    DROP FOREIGN KEY `organization_employee_dependent__reimbursement_wallet_fk`;
    """
    )

    op.execute(
        """
    ALTER TABLE `organization_employee_dependent`
    MODIFY COLUMN `reimbursement_wallet_id` bigint(20) DEFAULT NULL;
    """
    )

    op.execute(
        """
    ALTER TABLE `organization_employee_dependent`
    ADD CONSTRAINT `organization_employee_dependent__reimbursement_wallet_fk` 
    FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`) 
    ON DELETE CASCADE ON UPDATE CASCADE;
    """
    )
