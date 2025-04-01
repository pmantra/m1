"""create irs yearly statutory minumum deductible table in admin

Revision ID: e94548d562a7
Revises: 6731dc2b8206
Create Date: 2023-06-08 17:50:42.020741+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e94548d562a7"
down_revision = "6731dc2b8206"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "irs_minimum_deductible",
        sa.Column("year", sa.SmallInteger, primary_key=True, autoincrement=False),
        sa.Column("individual_amount", sa.Integer, nullable=False),
        sa.Column("family_amount", sa.Integer, nullable=False),
    )


def downgrade():
    op.drop_table("irs_minimum_deductible")
