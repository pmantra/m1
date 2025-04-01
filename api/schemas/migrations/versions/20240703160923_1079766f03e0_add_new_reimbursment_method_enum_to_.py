"""add new reimbursment_method enum to reimbursement_wallet

Revision ID: 1079766f03e0
Revises: 8f36a23826d9
Create Date: 2024-07-03 16:09:23.947905+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "1079766f03e0"
down_revision = "8f36a23826d9"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `reimbursement_wallet`
            MODIFY COLUMN reimbursement_method enum('DIRECT_DEPOSIT','PAYROLL', 'MMB_DIRECT_PAYMENT') COLLATE utf8mb4_unicode_ci,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `reimbursement_wallet`
            MODIFY COLUMN reimbursement_method enum('DIRECT_DEPOSIT','PAYROLL') COLLATE utf8mb4_unicode_ci,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
