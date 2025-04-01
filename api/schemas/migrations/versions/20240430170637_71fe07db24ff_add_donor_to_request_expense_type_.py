"""add donor to request expense type category

Revision ID: 71fe07db24ff
Revises: 640887c39dca
Create Date: 2024-04-30 17:06:37.103232+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "71fe07db24ff"
down_revision = "640887c39dca"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `reimbursement_request_category_expense_types`
            MODIFY COLUMN `expense_type` enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS', 'DONOR') COLLATE utf8mb4_unicode_ci NOT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `reimbursement_request_category_expense_types`
            MODIFY COLUMN expense_type enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS') COLLATE utf8mb4_unicode_ci NOT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
