"""add country code - currency code association

Revision ID: f43840ae5c78
Revises: 31a64daa2bf6
Create Date: 2023-04-26 15:07:55.369495+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f43840ae5c78"
down_revision = "31a64daa2bf6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "country_currency_code",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "country_alpha_2", sa.String(2), nullable=False, unique=True, index=True
        ),
        sa.Column("currency_code", sa.String(3), nullable=False),
    )


def downgrade():
    op.drop_table("country_currency_code")
