"""add_individual_or_family_plan_col_to_employee_health_plan

Revision ID: 929f151dda70
Revises: b064ab44c011
Create Date: 2023-08-03 20:35:13.450630+00:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "929f151dda70"
down_revision = "b064ab44c011"
branch_labels = None
depends_on = None


def upgrade():

    op.add_column(
        "employee_health_plan",
        sa.Column(
            "is_family_plan",
            sa.Boolean,
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("employee_health_plan", "is_family_plan")
