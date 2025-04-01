"""Add idp + external_id constraint to organization_external_id

Revision ID: 3e1ddc82ccfe
Revises: bf5408980bf9
Create Date: 2021-09-15 18:27:15.118685+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3e1ddc82ccfe"
down_revision = "bf5408980bf9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "idp_external_id", "organization_external_id", ["idp", "external_id"]
    )


def downgrade():
    op.drop_constraint("idp_external_id", "organization_external_id", type_="unique")
