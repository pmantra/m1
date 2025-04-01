"""Add insurer col to employee health plan table

Revision ID: 02890648bca4
Revises: a22605b1cf3b
Create Date: 2023-04-25 18:49:42.561867+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "02890648bca4"
down_revision = "a22605b1cf3b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "employee_health_plan", sa.Column("insurer", sa.String(50), nullable=False)
    )


def downgrade():
    op.drop_column("employee_health_plan", "insurer")
