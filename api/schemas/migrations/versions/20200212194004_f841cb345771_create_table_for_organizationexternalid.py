"""Create Table for OrganizationExternalID

Revision ID: f841cb345771
Revises: 
Create Date: 2020-02-12 19:40:04.437729

"""
from alembic import op
import sqlalchemy as sa
from models.enterprise import ExternalIDPNames


# revision identifiers, used by Alembic.
revision = "f841cb345771"
down_revision = "2e35353ca713"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization_external_id",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("idp", sa.Enum(ExternalIDPNames), nullable=False),
        sa.Column(
            "external_id",
            sa.String(120),
            nullable=False,
            doc="The unique identifier for an organization set by the IdP.",
        ),
        sa.Column("organization_id", sa.Integer, sa.ForeignKey("organization.id")),
    )


def downgrade():
    op.drop_table("organization_external_id")
