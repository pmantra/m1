"""add expense_type to reimbursement_request

Revision ID: bc5c6baafb07
Revises: 71fe07db24ff
Create Date: 2024-04-30 18:54:24.623816+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "bc5c6baafb07"
down_revision = "71fe07db24ff"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `reimbursement_request`
            ADD COLUMN expense_type enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS', 'DONOR') COLLATE utf8mb4_unicode_ci,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `reimbursement_request`
            DROP COLUMN expense_type,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
