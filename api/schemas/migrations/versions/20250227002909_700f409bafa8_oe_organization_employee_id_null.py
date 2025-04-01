"""oe-organization_employee_id-null

Revision ID: 700f409bafa8
Revises: 68439761c5a1
Create Date: 2025-02-27 00:29:09.303647+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "700f409bafa8"
down_revision = "68439761c5a1"
branch_labels = None
depends_on = None


def upgrade():
    """Make organization_employee_id column nullable."""
    op.alter_column(
        "member_track",
        "organization_employee_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade():
    """Revert organization_employee_id column to non-nullable."""
    op.alter_column(
        "member_track",
        "organization_employee_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
