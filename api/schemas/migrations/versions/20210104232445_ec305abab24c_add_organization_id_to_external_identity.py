"""Add organization_id to external identity

Revision ID: ec305abab24c
Revises: 51f9e5c95fef
Create Date: 2021-01-04 23:24:45.715765

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ec305abab24c"
down_revision = "51f9e5c95fef"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "external_identity",
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organization.id", name="external_identity_org_id_fk"),
        ),
    )


def downgrade():
    op.drop_constraint(
        "external_identity_org_id_fk", "external_identity", type_="foreignkey"
    )
    op.drop_column("external_identity", "organization_id")
