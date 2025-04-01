"""update_currency_code

Revision ID: e2b98f456b6e
Revises: 5051b388f9a5
Create Date: 2024-02-20 23:38:20.230254+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e2b98f456b6e"
down_revision = "5051b388f9a5"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_organization_settings_allowed_category
        DROP COLUMN currency_code,
        ADD COLUMN currency_code char(3) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_organization_settings_allowed_category
        DROP COLUMN currency_code,
        ADD COLUMN currency_code varchar(3) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
