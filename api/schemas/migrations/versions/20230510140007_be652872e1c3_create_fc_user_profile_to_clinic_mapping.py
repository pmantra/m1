"""create fc user profile to clinic mapping

Revision ID: be652872e1c3
Revises: 6fa47092c697
Create Date: 2023-05-10 14:00:07.223852+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "be652872e1c3"
down_revision = "6fa47092c697"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fertility_clinic_user_profile_fertility_clinic",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "fertility_clinic_id",
            sa.BigInteger,
            sa.ForeignKey("fertility_clinic.id"),
            nullable=False,
        ),
        sa.Column(
            "fertility_clinic_user_profile_id",
            sa.BigInteger,
            sa.ForeignKey("fertility_clinic_user_profile.id"),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "fertility_clinic_user_profile_fertility_clinic_uq_1",
        "fertility_clinic_user_profile_fertility_clinic",
        ["fertility_clinic_id", "fertility_clinic_user_profile_id"],
    )


def downgrade():
    op.drop_table("fertility_clinic_user_profile_fertility_clinic")
