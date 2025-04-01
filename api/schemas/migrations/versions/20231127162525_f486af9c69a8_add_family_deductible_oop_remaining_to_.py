"""add_family_deductible_oop_remaining_to_cost_breakdown

Revision ID: f486af9c69a8
Revises: 515534f32c49
Create Date: 2023-11-27 16:25:25.158339+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f486af9c69a8"
down_revision = "515534f32c49"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `cost_breakdown`
        ADD COLUMN `family_deductible_remaining` int(11) DEFAULT NULL,
        ADD COLUMN `family_oop_remaining` int(11) DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `cost_breakdown`
        DROP COLUMN `family_deductible_remaining`,
        DROP COLUMN `family_oop_remaining`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
