"""Add index to medications and rename to singular

Revision ID: 306a85934280
Revises: 62f9b764cfbd
Create Date: 2020-10-13 18:42:50.760054

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "306a85934280"
down_revision = "62f9b764cfbd"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("medications", "medication")
    op.create_index("proprietary_name_idx", "medication", ["proprietary_name"])


def downgrade():
    op.drop_index("proprietary_name_idx", "medication")
    op.rename_table("medication", "medications")
