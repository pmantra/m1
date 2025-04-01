"""Add program_operations_staff to roles

Revision ID: cbee1290701b
Revises: a8514392e3d4
Create Date: 2021-10-18 21:59:33.853325+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "cbee1290701b"
down_revision = "a8514392e3d4"
branch_labels = None
depends_on = None

OLD_ROLES = (
    "banned_member",
    "member",
    "practitioner",
    "moderator",
    "staff",
    "marketing_staff",
    "payments_staff",
    "producer",
    "superuser",
    "care_coordinator",
    "care_coordinator_manager",
)

ROLES = OLD_ROLES + ("program_operations_staff",)


def upgrade():
    op.alter_column(
        "role",
        "name",
        type_=sa.Enum(*ROLES),
        existing_type=sa.Enum(*OLD_ROLES),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "role",
        "name",
        type_=sa.Enum(*OLD_ROLES),
        existing_type=sa.Enum(*ROLES),
        nullable=False,
    )
