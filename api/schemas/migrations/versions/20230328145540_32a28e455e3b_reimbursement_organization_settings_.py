"""reimbursement_organization_settings_cycles_enabled

Revision ID: 32a28e455e3b
Revises: 81cdab83bb0a
Create Date: 2023-03-28 14:55:40.503303+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "32a28e455e3b"
down_revision = "3b93b7ef5abe"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_organization_settings",
        sa.Column("cycles_enabled", sa.Boolean, nullable=False, default=False),
    )


def downgrade():
    op.drop_column("reimbursement_organization_settings", "cycles_enabled")
