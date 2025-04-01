"""add rte transaction table

Revision ID: 06d55e050598
Revises: 208fc9c3ec0d
Create Date: 2023-05-10 15:49:12.415131+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "06d55e050598"
down_revision = "208fc9c3ec0d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rte_transaction",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "employee_health_plan_id",
            sa.BigInteger,
            sa.ForeignKey("employee_health_plan.id"),
            nullable=False,
        ),
        sa.Column("response_code", sa.BigInteger, nullable=False),
        sa.Column("request", sa.Text, nullable=False),
        sa.Column("response", sa.Text, nullable=True),
        sa.Column("plan_active_status", sa.Boolean, nullable=True),
        sa.Column("error_message", sa.Text(1000), nullable=True),
        sa.Column("time", sa.TIMESTAMP, nullable=False),
    )


def downgrade():
    op.drop_table("rte_transaction")
