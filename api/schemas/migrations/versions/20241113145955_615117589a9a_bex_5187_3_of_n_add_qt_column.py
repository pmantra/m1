"""BEX-5187_3_of_n_add_qt_column

Revision ID: 615117589a9a
Revises: 2aed10582284
Create Date: 2024-11-13 14:59:55.835878+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "615117589a9a"
down_revision = "2aed10582284"
branch_labels = None
depends_on = None


def upgrade():
    query = """
        ALTER TABLE annual_insurance_questionnaire_response
        ADD COLUMN questionnaire_type ENUM(
        'TRADITIONAL_HDHP',
        'DIRECT_PAYMENT_HDHP',
        'DIRECT_PAYMENT_HEALTH_INSURANCE',
        'DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER',
        'LEGACY'
        ) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'LEGACY',
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    op.execute(query)


def downgrade():
    query = """
        ALTER TABLE annual_insurance_questionnaire_response 
        DROP COLUMN questionnaire_type,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    op.execute(query)
