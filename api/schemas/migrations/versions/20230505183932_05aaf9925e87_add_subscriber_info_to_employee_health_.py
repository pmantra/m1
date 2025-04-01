"""add subscriber info to employee health plan table

Revision ID: 05aaf9925e87
Revises: 9bd2240628ce
Create Date: 2023-05-05 18:39:32.253766+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "05aaf9925e87"
down_revision = "9bd2240628ce"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "employee_health_plan",
        sa.Column("subscriber_first_name", sa.String(50), nullable=True),
    )
    op.add_column(
        "employee_health_plan",
        sa.Column("subscriber_last_name", sa.String(50), nullable=True),
    )
    op.add_column(
        "employee_health_plan",
        sa.Column("subscriber_date_of_birth", sa.Date, nullable=True),
    )


def downgrade():
    op.drop_column("employee_health_plan", "subscriber_first_name")
    op.drop_column("employee_health_plan", "subscriber_last_name")
    op.drop_column("employee_health_plan", "subscriber_date_of_birth")
