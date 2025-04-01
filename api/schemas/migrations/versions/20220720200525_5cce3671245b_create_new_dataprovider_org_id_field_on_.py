"""Create new dataprovider-org-id field on organization_external_id

Revision ID: 5cce3671245b
Revises: 6aa151532c8b
Create Date: 2022-07-20 20:05:25.231162+00:00

"""
from alembic import op
import sqlalchemy as sa
from models.enterprise import ExternalIDPNames

# revision identifiers, used by Alembic.
revision = "5cce3671245b"
down_revision = "6aa151532c8b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organization_external_id",
        sa.Column(
            "data_provider_organization_id",
            sa.Integer,
            nullable=True,
            doc="Unique identifier tying to the organization ID providing the data this mapping of externalID:maven Org ID applies to",
        ),
    )
    op.add_column(
        "organization_external_id",
        sa.Column(
            "identity_provider_id",
            sa.Integer,
            nullable=True,
            doc="Unique identifier tying to the identity provider ID which maintains this mapping of externalID:maven Org ID applies to",
        ),
    )
    op.alter_column(
        "organization_external_id",
        "idp",
        nullable=True,
        existing_type=sa.Enum(ExternalIDPNames),
    )


def downgrade():
    op.drop_column("organization_external_id", "data_provider_organization_id")
    op.drop_column("organization_external_id", "identity_provider_id")
    op.alter_column(
        "organization_external_id",
        "idp",
        nullable=False,
        existing_type=sa.Enum(ExternalIDPNames),
    )
