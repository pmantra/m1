"""backfill in_house_fullfillment to equal True

Revision ID: d4a91b81202a
Revises: 7946c3528587
Create Date: 2020-10-28 22:42:35.716541

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4a91b81202a"
down_revision = "7946c3528587"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE bms_order SET is_maven_in_house_fulfillment = true WHERE is_maven_in_house_fulfillment IS NULL"
    )
    op.alter_column(
        "bms_order",
        "is_maven_in_house_fulfillment",
        existing_type=sa.Boolean,
        nullable=False,
        default=False,
        server_default=sa.sql.expression.false(),
    )


def downgrade():
    op.alter_column(
        "bms_order",
        "is_maven_in_house_fulfillment",
        existing_type=sa.Boolean,
        nullable=True,
        default=False,
    )
