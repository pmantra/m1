"""Add_country_code_to_ca_member_match_log

Revision ID: 4229047780f5
Revises: 5717819ea650
Create Date: 2022-10-20 17:18:59.876211+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4229047780f5"
down_revision = "5717819ea650"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ca_member_match_log", sa.Column("country_code", sa.String(2), nullable=True)
    )


def downgrade():
    op.drop_column("ca_member_match_log", "country_code")
