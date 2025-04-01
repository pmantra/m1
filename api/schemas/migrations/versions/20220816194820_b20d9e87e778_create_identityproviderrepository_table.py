"""Create IdentityProviderRepository table

Revision ID: b20d9e87e778
Revises: 2c7ec8af28ef
Create Date: 2022-08-16 19:48:20.096432+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b20d9e87e778"
down_revision = "2c7ec8af28ef"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "identity_provider_repository",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("name", sa.String(120), nullable=True),
    )


def downgrade():
    op.drop_table("identity_provider_repository")
