"""fertility portal roles

Revision ID: 8f0f5b10286b
Revises: 06d55e050598
Create Date: 2023-05-23 15:09:21.692899+00:00

"""

import enum

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "8f0f5b10286b"
down_revision = "06d55e050598"
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
    content_admin = "content_admin"


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
    fertility_clinic_user = "fertility_clinic_user"
    fertility_clinic_billing_user = "fertility_clinic_billing_user"


def upgrade():
    op.alter_column(
        "role",
        "name",
        type_=sa.Enum(NewRoleName),
        existing_type=sa.Enum(OldRoleName),
        nullable=False,
    )
    op.execute(
        "INSERT INTO role (name) values ('fertility_clinic_user'), ('fertility_clinic_billing_user');"
    )


def downgrade():
    op.execute(
        "DELETE FROM role where name in ('fertility_clinic_user', 'fertility_clinic_billing_user');"
    )
    op.alter_column(
        "role",
        "name",
        type_=sa.Enum(OldRoleName),
        existing_type=sa.Enum(NewRoleName),
        nullable=False,
    )
