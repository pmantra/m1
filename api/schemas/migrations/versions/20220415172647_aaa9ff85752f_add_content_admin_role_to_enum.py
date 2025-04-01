"""Add content admin role to enum

Revision ID: aaa9ff85752f
Revises: 7a66039bb935
Create Date: 2022-04-15 17:26:47.850817+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "aaa9ff85752f"
down_revision = "7a66039bb935"
branch_labels = None
depends_on = None


class OldRoleName(enum.Enum):
    banned_member = "banned_member"
    member = "member"
    practitioner = "practitioner"
    moderator = "moderator"
    staff = "staff"
    marketing_staff = "marketing_staff"
    payments_staff = "payments_staff"
    producer = "producer"
    superuser = "superuser"
    care_coordinator = "care_coordinator"
    care_coordinator_manager = "care_coordinator_manager"
    program_operations_staff = "program_operations_staff"


class NewRoleName(enum.Enum):
    banned_member = "banned_member"
    member = "member"
    practitioner = "practitioner"
    moderator = "moderator"
    staff = "staff"
    marketing_staff = "marketing_staff"
    payments_staff = "payments_staff"
    producer = "producer"
    superuser = "superuser"
    care_coordinator = "care_coordinator"
    care_coordinator_manager = "care_coordinator_manager"
    program_operations_staff = "program_operations_staff"
    content_admin = "content_admin"


def upgrade():
    op.alter_column(
        "role",
        "name",
        type_=sa.Enum(NewRoleName),
        existing_type=sa.Enum(OldRoleName),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "role",
        "name",
        type_=sa.Enum(OldRoleName),
        existing_type=sa.Enum(NewRoleName),
        nullable=False,
    )
