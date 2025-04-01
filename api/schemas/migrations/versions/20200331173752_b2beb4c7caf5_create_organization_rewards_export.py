"""Create table for OrganizationRewardsExport

Revision ID: b2beb4c7caf5
Revises: d316ca01ed14
Create Date: 2020-03-31 17:37:52.981713

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b2beb4c7caf5"
down_revision = "d316ca01ed14"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization_rewards_export",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
        sa.Column(
            "organization_external_id_id",
            sa.Integer,
            sa.ForeignKey("organization_external_id.id"),
        ),
    )


def downgrade():
    op.drop_table("organization_rewards_export")
