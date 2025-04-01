"""add_rw_id_col_to_oed_table

Revision ID: d7a8b7b444c9
Revises: 6ae1e553086d
Create Date: 2023-10-27 16:05:17.973708+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "d7a8b7b444c9"
down_revision = "f49dd5f4e5fd"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    ALTER TABLE `organization_employee_dependent`
    ADD COLUMN `reimbursement_wallet_id` BIGINT(20) DEFAULT NULL,
    ALGORITHM=INPLACE,
    LOCK=NONE;
    """
    )


def downgrade():
    op.execute(
        """
    ALTER TABLE `organization_employee_dependent`
    DROP COLUMN `reimbursement_wallet_id`,
    ALGORITHM=INPLACE,
    LOCK=NONE;
    """
    )
