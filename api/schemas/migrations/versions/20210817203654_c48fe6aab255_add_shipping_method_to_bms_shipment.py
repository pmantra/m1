"""Add shipping method to bms_shipment

Revision ID: c48fe6aab255
Revises: 0a709ebb00b3
Create Date: 2021-08-17 20:36:54.389475+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c48fe6aab255"
down_revision = "0a709ebb00b3"
branch_labels = None
depends_on = None


class ShippingMethods(enum.Enum):
    UPS_GROUND = "UPS Ground"
    UPS_3_DAY_SELECT = "UPS 3 Day Select"
    UPS_2_DAY = "UPS 2 Day"
    UPS_1_DAY = "UPS 1 Day"
    UPS_NEXT_DAY_AIR = "UPS Next Day Air"
    UPS_WORLDWIDE_EXPRESS = "UPS Worldwide Express"


def upgrade():
    op.add_column(
        "bms_shipment",
        sa.Column("shipping_method", sa.Enum(ShippingMethods), nullable=True),
    )


def downgrade():
    op.drop_column("bms_shipment", "shipping_method")
