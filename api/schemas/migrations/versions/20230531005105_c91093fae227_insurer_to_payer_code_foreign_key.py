"""insurer_to_payer_code_foreign_key

Revision ID: c91093fae227
Revises: ccf79c3d408b
Create Date: 2023-05-31 00:51:05.937777+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c91093fae227"
down_revision = "ccf79c3d408b"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "employee_health_plan",
        "insurer",
        type_=sa.BigInteger,
        existing_type=sa.String,
        nullable=False,
    )
    op.create_foreign_key(
        None, "employee_health_plan", "rte_payer_list", ["insurer"], ["id"]
    )


def downgrade():
    op.drop_constraint(
        "employee_health_plan_ibfk_3", "employee_health_plan", type="foreignkey"
    )
    op.alter_column(
        "employee_health_plan",
        "insurer",
        type_=sa.String(20),
        existing_type=sa.Integer,
        nullable=False,
    )
