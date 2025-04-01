"""Add required_track column to reimbursement_organization_settings

Revision ID: 474bedcd802e
Revises: ec305abab24c
Create Date: 2021-01-05 17:17:17.735785

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "474bedcd802e"
down_revision = "ec305abab24c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_organization_settings",
        sa.Column("required_track", sa.String(120), nullable=True),
    )


def downgrade():
    op.drop_column("reimbursement_organization_settings", "required_track")
