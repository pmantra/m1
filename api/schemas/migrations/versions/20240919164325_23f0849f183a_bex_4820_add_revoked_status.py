"""BEX-4820-add-revoked-status

Revision ID: 23f0849f183a
Revises: 78957965e950
Create Date: 2024-09-19 16:43:25.281018+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "23f0849f183a"
down_revision = "78957965e950"
branch_labels = None
depends_on = None


def upgrade():
    # Modify the column to include the new enum value
    op.execute(
        """
    ALTER TABLE reimbursement_wallet_users
    MODIFY COLUMN status ENUM('PENDING', 'ACTIVE', 'DENIED', 'REVOKED')
    NOT NULL,
    ALGORITHM=COPY;
    """
    )


def downgrade():
    op.execute(
        """
    ALTER TABLE reimbursement_wallet_users
    MODIFY COLUMN status ENUM('PENDING', 'ACTIVE', 'DENIED') NOT NULL,
    ALGORITHM=COPY;
    """
    )
