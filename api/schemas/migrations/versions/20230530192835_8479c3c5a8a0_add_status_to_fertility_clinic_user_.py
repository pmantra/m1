"""Add status to fertility_clinic_user_profile

Revision ID: 8479c3c5a8a0
Revises: 6457ba93b77d
Create Date: 2023-05-30 19:28:35.739474+00:00

"""
from alembic import op
import sqlalchemy as sa
import enum

# revision identifiers, used by Alembic.
revision = "8479c3c5a8a0"
down_revision = "6457ba93b77d"
branch_labels = None
depends_on = None


def upgrade():
    class AccountStatus(enum.Enum):
        ACTIVE = "ACTIVE"
        INACTIVE = "INACTIVE"
        SUSPENDED = "SUSPENDED"

    op.add_column(
        "fertility_clinic_user_profile",
        sa.Column("status", sa.Enum(AccountStatus), nullable=False),
    )


def downgrade():
    op.drop_column("fertility_clinic_user_profile", "status")
