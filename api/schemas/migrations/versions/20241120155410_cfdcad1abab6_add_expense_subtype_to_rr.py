"""Add expense subtype to RR

Revision ID: cfdcad1abab6
Revises: 464bd3c9a4aa
Create Date: 2024-11-20 15:54:10.875081+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "cfdcad1abab6"
down_revision = "464bd3c9a4aa"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `reimbursement_request`
            ADD COLUMN `original_expense_type` enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR','PRESERVATION') COLLATE utf8mb4_unicode_ci DEFAULT NULL AFTER `expense_type`,
            ADD COLUMN `wallet_expense_subtype_id` int(11) DEFAULT NULL,
            ADD COLUMN `original_wallet_expense_subtype_id` int(11) DEFAULT NULL,
            ADD CONSTRAINT `reimbursement_request_ibfk_5` FOREIGN KEY (`wallet_expense_subtype_id`) REFERENCES `wallet_expense_subtype` (`id`),
            ADD CONSTRAINT `reimbursement_request_ibfk_6` FOREIGN KEY (`original_wallet_expense_subtype_id`) REFERENCES `wallet_expense_subtype` (`id`),
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `reimbursement_request`
            DROP FOREIGN KEY `reimbursement_request_ibfk_5`,
            DROP FOREIGN KEY `reimbursement_request_ibfk_6`;
            
            ALTER TABLE `reimbursement_request`
            DROP COLUMN original_expense_type,
            DROP COLUMN wallet_expense_subtype_id,
            DROP COLUMN original_wallet_expense_subtype_id,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
