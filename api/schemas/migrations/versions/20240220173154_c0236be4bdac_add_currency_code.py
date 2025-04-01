"""add_currency_code_to_reimbursement_organization_settings_allowed_category

Revision ID: c0236be4bdac
Revises: 2527df8369b5
Create Date: 2024-02-20 17:31:54.043491+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c0236be4bdac"
down_revision = "a3ae80627328"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_organization_settings_allowed_category
        ADD COLUMN currency_code varchar(3) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_organization_settings_allowed_category
        DROP COLUMN currency_code,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
        """
    )
