"""Add organization_email_domain table

Revision ID: 864747f2d111
Revises: f841cb345771
Create Date: 2020-02-13 15:48:42.925420

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "864747f2d111"
down_revision = "f841cb345771"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization_email_domain",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("domain", sa.String(120), unique=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organization.id"),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_table("organization_email_domain")
