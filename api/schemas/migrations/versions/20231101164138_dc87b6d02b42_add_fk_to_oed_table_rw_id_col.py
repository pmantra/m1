"""add_fk_to_oed_table_rw_id_col

Revision ID: dc87b6d02b42
Revises: 53ac6940663d
Create Date: 2023-11-01 16:41:38.417772+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "dc87b6d02b42"
down_revision = "e24dc1396354"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    ALTER TABLE `organization_employee_dependent`
        ADD CONSTRAINT `organization_employee_dependent__reimbursement_wallet_fk` 
        FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE;
    """
    )


def downgrade():
    op.execute(
        """
    ALTER TABLE `organization_employee_dependent`
        DROP FOREIGN KEY `organization_employee_dependent__reimbursement_wallet_fk`,
        ALGORITHM=INPLACE, LOCK=NONE  
    """
    )
