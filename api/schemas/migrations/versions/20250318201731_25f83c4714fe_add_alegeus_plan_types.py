"""add-alegeus-plan-types

Revision ID: 25f83c4714fe
Revises: f455a9a022c3
Create Date: 2025-03-18 20:17:31.210728+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "25f83c4714fe"
down_revision = "f455a9a022c3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_plan
        MODIFY COLUMN plan_type enum('LIFETIME','ANNUAL','HYBRID','PER_EVENT') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_plan
        MODIFY COLUMN plan_type enum('LIFETIME','ANNUAL') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
