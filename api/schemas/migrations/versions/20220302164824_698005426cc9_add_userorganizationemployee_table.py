"""Add UserOrganizationEmployee table

Revision ID: 698005426cc9
Revises: 4bafe3966f5f
Create Date: 2022-03-02 16:48:24.898114+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "698005426cc9"
down_revision = "113f21b24a21"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_organization_employee",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("user.id"),
        ),
        sa.Column(
            "organization_employee_id",
            sa.Integer,
            sa.ForeignKey("organization_employee.id"),
        ),
        sa.Column("ended_at", sa.DateTime),
    )


def downgrade():
    op.drop_table("user_organization_employee")
