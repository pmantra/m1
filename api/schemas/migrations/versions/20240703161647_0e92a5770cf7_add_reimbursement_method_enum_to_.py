"""add reimbursement_method enum to expense_types config

Revision ID: 0e92a5770cf7
Revises: 1079766f03e0
Create Date: 2024-07-03 16:16:47.420386+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0e92a5770cf7"
down_revision = "1079766f03e0"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `reimbursement_organization_settings_expense_types`
            MODIFY COLUMN reimbursement_method enum('DIRECT_DEPOSIT','PAYROLL', 'MMB_DIRECT_PAYMENT') COLLATE utf8mb4_unicode_ci,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `reimbursement_organization_settings_expense_types`
            MODIFY COLUMN reimbursement_method enum('DIRECT_DEPOSIT','PAYROLL') COLLATE utf8mb4_unicode_ci,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
