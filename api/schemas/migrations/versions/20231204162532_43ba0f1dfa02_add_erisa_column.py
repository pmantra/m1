"""Add ERISA column

Revision ID: 43ba0f1dfa02
Revises: e5159e6dfee6
Create Date: 2023-12-04 16:25:32.881654+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "43ba0f1dfa02"
down_revision = "e5159e6dfee6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_request`
        ADD COLUMN `erisa_workflow` tinyint(1) NOT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_request`
        DROP COLUMN `erisa_workflow`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
