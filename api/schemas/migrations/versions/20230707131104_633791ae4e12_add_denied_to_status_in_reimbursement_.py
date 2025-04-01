"""add_denied_to_status_in_reimbursement_wallet_users

Revision ID: 633791ae4e12
Revises: f5321cff79cd
Create Date: 2023-07-07 13:11:04.723045+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "633791ae4e12"
down_revision = "f5321cff79cd"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """ALTER TABLE reimbursement_wallet_users
        MODIFY COLUMN status ENUM("PENDING", "ACTIVE", "DENIED") NOT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """ALTER TABLE reimbursement_wallet_users 
        MODIFY COLUMN status ENUM("PENDING", "ACTIVE") NOT NULL;
        """
    )
