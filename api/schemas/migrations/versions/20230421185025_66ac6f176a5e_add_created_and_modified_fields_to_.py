"""Add created and modified fields to employee and employer health plans

Revision ID: 66ac6f176a5e
Revises: 71e8c9a36b8e
Create Date: 2023-04-21 18:50:25.646822+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "66ac6f176a5e"
down_revision = "71e8c9a36b8e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("employer_health_plan", sa.Column("created_at", sa.DateTime))
    op.add_column("employer_health_plan", sa.Column("modified_at", sa.DateTime))

    op.add_column("employee_health_plan", sa.Column("created_at", sa.DateTime))
    op.add_column("employee_health_plan", sa.Column("modified_at", sa.DateTime))

    op.add_column(
        "employer_health_plan_cost_sharing", sa.Column("created_at", sa.DateTime)
    )
    op.add_column(
        "employer_health_plan_cost_sharing", sa.Column("modified_at", sa.DateTime)
    )


def downgrade():
    op.drop_column("employer_health_plan", "created_at")
    op.drop_column("employer_health_plan", "modified_at")

    op.drop_column("employee_health_plan", "created_at")
    op.drop_column("employee_health_plan", "modified_at")

    op.drop_column("employer_health_plan_cost_sharing", "created_at")
    op.drop_column("employer_health_plan_cost_sharing", "modified_at")
