"""Add identity_provider_id and external_organization_id to ExternalIdentity table

Revision ID: 2c7ec8af28ef
Revises: 3130938c18af
Create Date: 2022-08-16 18:32:02.267205+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2c7ec8af28ef"
down_revision = "3130938c18af"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("external_identity") as batch_op:
        batch_op.add_column(
            sa.Column("identity_provider_id", sa.Integer, nullable=True)
        )
        batch_op.add_column(
            sa.Column("external_organization_id", sa.Integer, nullable=True)
        )
        batch_op.create_index("idx_identity_provider_id", ["identity_provider_id"])
        batch_op.create_index(
            "idx_external_organization_id", ["external_organization_id"]
        )


def downgrade():
    with op.batch_alter_table("external_identity") as batch_op:
        batch_op.drop_column("identity_provider_id")
        batch_op.drop_column("external_organization_id")
        batch_op.drop_index("idx_identity_provider_id")
        batch_op.drop_index("idx_external_organization_id")
