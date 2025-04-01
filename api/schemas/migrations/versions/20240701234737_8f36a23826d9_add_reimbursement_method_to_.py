"""add reimbursement_method to reimbursement_request

Revision ID: 8f36a23826d9
Revises: b99dd1c670dc
Create Date: 2024-07-01 23:47:37.560773+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "8f36a23826d9"
down_revision = "b99dd1c670dc"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `reimbursement_request`
            ADD COLUMN reimbursement_method enum('DIRECT_DEPOSIT','PAYROLL', 'MMB_DIRECT_PAYMENT') COLLATE utf8mb4_unicode_ci,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `reimbursement_request`
            DROP COLUMN reimbursement_method,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
