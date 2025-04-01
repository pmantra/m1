"""Update BMS shipment shipping method enum

Revision ID: 5e05b875fe54
Revises: c3907b62ef6f
Create Date: 2022-09-16 18:11:58.044514+00:00

"""
from alembic import op
import sqlalchemy as sa
import enum

from bms.models.bms import BMSShipment

# revision identifiers, used by Alembic.
revision = "5e05b875fe54"
down_revision = "c3907b62ef6f"
branch_labels = None
depends_on = None


class OldShippingMethods(enum.Enum):
    UPS_GROUND = "UPS Ground"
    UPS_3_DAY_SELECT = "UPS 3 Day Select"
    UPS_2_DAY = "UPS 2nd Day Air"
    UPS_1_DAY = "UPS 1 Day"
    UPS_NEXT_DAY_AIR = "UPS Next Day Air"
    UPS_WORLDWIDE_EXPRESS = "UPS Worldwide Express"


class NewShippingMethods(enum.Enum):
    UPS_GROUND = "UPS Ground"
    UPS_3_DAY_SELECT = "UPS 3 Day Select"
    UPS_2_DAY = "UPS 2nd Day Air"
    UPS_1_DAY = "UPS 1 Day"
    UPS_NEXT_DAY_AIR = "UPS Next Day Air"
    UPS_WORLDWIDE_EXPRESS = "UPS Worldwide Express"
    UPS_WORLDWIDE_EXPEDITED = "UPS Worldwide Expedited"


def upgrade():
    op.alter_column(
        BMSShipment.__tablename__,
        "shipping_method",
        existing_type=sa.Enum(OldShippingMethods),
        type_=sa.Enum(NewShippingMethods),
    )


def downgrade():
    op.alter_column(
        BMSShipment.__tablename__,
        "shipping_method",
        existing_type=sa.Enum(NewShippingMethods),
        type_=sa.Enum(OldShippingMethods),
    )
