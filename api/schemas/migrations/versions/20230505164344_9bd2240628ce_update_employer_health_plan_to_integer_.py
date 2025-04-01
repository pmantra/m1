"""update employer health plan to integer amounts

Revision ID: 9bd2240628ce
Revises: 00b675e0cdeb
Create Date: 2023-05-05 16:43:44.183904+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "9bd2240628ce"
down_revision = "00b675e0cdeb"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan_cost_sharing`
        DROP COLUMN `dollar_amount`,
        ADD COLUMN `absolute_amount` INTEGER,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan_cost_sharing`
        DROP COLUMN `absolute_amount`,
        ADD COLUMN `dollar_amount` NUMERIC(6, 2),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
