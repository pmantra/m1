"""add_wallet_state_enum

Revision ID: 51abacd7d153
Revises: 4ec05db2cfe1
Create Date: 2023-06-28 14:33:29.410783+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "51abacd7d153"
down_revision = "4ec05db2cfe1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """ALTER TABLE reimbursement_wallet
        MODIFY COLUMN state ENUM("PENDING", "QUALIFIED", "DISQUALIFIED", "EXPIRED", "RUNOUT") NOT NULL DEFAULT 'PENDING',
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE reimbursement_wallet 
        MODIFY COLUMN state ENUM("PENDING", "QUALIFIED", "DISQUALIFIED", "EXPIRED") NOT NULL DEFAULT "PENDING";
    """
    )
