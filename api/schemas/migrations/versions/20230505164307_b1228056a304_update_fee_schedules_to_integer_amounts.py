"""update fee schedules to integer amounts

Revision ID: b1228056a304
Revises: 00de519b7293
Create Date: 2023-05-05 16:43:07.641811+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b1228056a304"
down_revision = "00de519b7293"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "fee_schedule_global_procedures",
        "cost",
        type_=sa.Integer,
        existing_type=sa.DECIMAL(precision=8, scale=2),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "fee_schedule_global_procedures",
        "cost",
        type_=sa.DECIMAL(precision=8, scale=2),
        existing_type=sa.Integer,
        nullable=False,
    )
