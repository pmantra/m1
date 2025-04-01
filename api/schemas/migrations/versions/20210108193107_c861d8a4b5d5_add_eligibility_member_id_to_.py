"""Add eligibility_member_id to organization_employee

Revision ID: c861d8a4b5d5
Revises: 474bedcd802e
Create Date: 2021-01-08 19:31:07.610259

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c861d8a4b5d5"
down_revision = "474bedcd802e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organization_employee",
        sa.Column("eligibility_member_id", sa.Integer, nullable=True),
    )
    op.create_index(
        "idx_eligibility_member_id", "organization_employee", ["eligibility_member_id"]
    )


def downgrade():
    op.drop_index("idx_eligibility_member_id", table_name="organization_employee")
    op.drop_column("organization_employee", "eligibility_member_id")
