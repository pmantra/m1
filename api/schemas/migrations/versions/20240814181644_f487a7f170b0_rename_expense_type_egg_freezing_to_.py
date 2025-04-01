"""rename expense type egg_freezing to preservation

Revision ID: f487a7f170b0
Revises: e74b7a0584e3
Create Date: 2024-08-14 18:16:44.807563+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f487a7f170b0"
down_revision = "fb4f2099a9a4"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `reimbursement_request_category_expense_types`
            MODIFY COLUMN `expense_type` enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR','PRESERVATION') COLLATE utf8mb4_unicode_ci NOT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
            
            ALTER TABLE `reimbursement_request`
            MODIFY COLUMN `expense_type` enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR','PRESERVATION') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
            
            ALTER TABLE `reimbursement_wallet`
            MODIFY COLUMN `primary_expense_type` enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR','PRESERVATION') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
            
            ALTER TABLE `reimbursement_organization_settings_expense_types`
            MODIFY COLUMN `expense_type` enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR','PRESERVATION') COLLATE utf8mb4_unicode_ci NOT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `reimbursement_organization_settings_expense_types`
            MODIFY COLUMN expense_type enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR') COLLATE utf8mb4_unicode_ci NOT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
            
            ALTER TABLE `reimbursement_wallet`
            MODIFY COLUMN expense_type enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            ALGORITHM=COPY, LOCK=SHARED;

            ALTER TABLE `reimbursement_request`
            MODIFY COLUMN expense_type enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
            
            ALTER TABLE `reimbursement_request_category_expense_types`
            MODIFY COLUMN expense_type enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR') COLLATE utf8mb4_unicode_ci NOT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
