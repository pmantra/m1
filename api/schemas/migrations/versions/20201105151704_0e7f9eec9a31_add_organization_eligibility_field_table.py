"""Add organization_eligibility_field table

Revision ID: 0e7f9eec9a31
Revises: d4a91b81202a
Create Date: 2020-11-05 15:17:04.124150

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0e7f9eec9a31"
down_revision = "d4a91b81202a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization_eligibility_field",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organization.id", name="eligibility_field_org_id_fk"),
            nullable=False,
        ),
        sa.UniqueConstraint("organization_id", "name"),
    )


def downgrade():
    op.drop_table("organization_eligibility_field")
