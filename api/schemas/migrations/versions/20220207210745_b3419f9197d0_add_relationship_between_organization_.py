"""Add relationship between Organization and Agreement

Revision ID: b3419f9197d0
Revises: 1bef8e26445d
Create Date: 2022-02-07 21:07:45.489671+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3419f9197d0"
down_revision = "1bef8e26445d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization_agreements",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organization.id"),
        ),
        sa.Column(
            "agreement_id",
            sa.Integer,
            sa.ForeignKey("agreement.id"),
        ),
    )


def downgrade():
    op.drop_table("organization_agreements")
