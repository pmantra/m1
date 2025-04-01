"""Add new org emp insurer eligibility table

Revision ID: 27526ef71ab6
Revises: 6c4cef845e99
Create Date: 2020-04-22 17:08:54.257365

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "27526ef71ab6"
down_revision = "6c4cef845e99"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization_employee_insurer_eligibility",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
        sa.Column("edi_271", sa.Text, nullable=False, default=""),
        sa.Column("information_source", sa.String(120), nullable=False, default=""),
        sa.Column(
            "organization_employee_id",
            sa.Integer,
            sa.ForeignKey("organization_employee.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_table("organization_employee_insurer_eligibility")
