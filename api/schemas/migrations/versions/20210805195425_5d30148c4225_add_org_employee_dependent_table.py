"""Add org employee dependent table

Revision ID: 5d30148c4225
Revises: 6789198ef664
Create Date: 2021-08-05 19:54:25.119227+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5d30148c4225"
down_revision = "6789198ef664"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization_employee_dependent",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "organization_employee_id",
            sa.Integer,
            sa.ForeignKey("organization_employee.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("first_name", sa.VARCHAR(40), nullable=True),
        sa.Column("last_name", sa.VARCHAR(40), nullable=True),
        sa.Column("middle_name", sa.VARCHAR(40), nullable=True),
        sa.Column("modified_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime),
        sa.Column("alegeus_dependent_id", sa.VARCHAR(30), nullable=True),
    )
    op.create_unique_constraint(
        "alegeus_dependent_id",
        "organization_employee_dependent",
        ["alegeus_dependent_id"],
    )


def downgrade():
    op.drop_table("organization_employee_dependent")
