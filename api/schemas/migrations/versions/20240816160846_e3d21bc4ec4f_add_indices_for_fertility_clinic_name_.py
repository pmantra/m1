"""add indices for fertility clinic name and for fertility clinic location name

Revision ID: e3d21bc4ec4f
Revises: a186ec792b4d
Create Date: 2024-08-16 16:08:46.991617+00:00

"""
from alembic import op


# revision identifiers, used by Alembic
revision = "e3d21bc4ec4f"
down_revision = "a186ec792b4d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_fertility_clinic_name", "fertility_clinic", ["name"])
    op.create_index(
        "ix_fertility_clinic_location_name", "fertility_clinic_location", ["name"]
    )


def downgrade():
    op.drop_index("ix_fertility_clinic_name", "fertility_clinic")
    op.drop_index("ix_fertility_clinic_location_name", "fertility_clinic_location")
