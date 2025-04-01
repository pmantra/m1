"""Add invite type

Revision ID: 8f5b9f6e4dd3
Revises: 249ba852505a
Create Date: 2021-03-15 21:16:24.624185

"""
from alembic import op
import sqlalchemy as sa
import enum


# revision identifiers, used by Alembic.
revision = "8f5b9f6e4dd3"
down_revision = "249ba852505a"
branch_labels = None
depends_on = None


def upgrade():
    class InviteType(str, enum.Enum):
        PARTNER = "PARTNER"
        FILELESS_EMPLOYEE = "FILELESS_EMPLOYEE"
        FILELESS_DEPENDENT = "FILELESS_DEPENDENT"

    op.add_column(
        "invite",
        sa.Column(
            "type", sa.String(255), nullable=False, server_default=InviteType.PARTNER
        ),
    )


def downgrade():
    op.drop_column("invite", "type")
