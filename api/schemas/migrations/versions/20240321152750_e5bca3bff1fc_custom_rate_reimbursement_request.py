"""custom_rate_reimbursement_request

Revision ID: e5bca3bff1fc
Revises: ab02eff69511
Create Date: 2024-03-08 15:27:50.321957+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e5bca3bff1fc"
down_revision = "e32837c1e35a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_request
        ADD COLUMN use_custom_rate BOOLEAN DEFAULT FALSE,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_request
        DROP COLUMN use_custom_rate,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
