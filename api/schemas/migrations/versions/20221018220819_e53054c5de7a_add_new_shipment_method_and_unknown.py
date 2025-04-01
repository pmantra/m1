"""add_new_shipment_method_and_unknown

Revision ID: e53054c5de7a
Revises: 13de312f2e79
Create Date: 2022-10-18 22:08:19.204719+00:00

"""
from alembic import op
import sqlalchemy as sa
import enum

from bms.models.bms import BMSShipment

# revision identifiers, used by Alembic.
revision = "e53054c5de7a"
down_revision = "13de312f2e79"
branch_labels = None
depends_on = None


class NewShippingMethods(enum.Enum):
    UPS_GROUND = "UPS Ground"
    UPS_3_DAY_SELECT = "UPS 3 Day Select"
    UPS_2_DAY = "UPS 2nd Day Air"
    UPS_1_DAY = "UPS 1 Day"
    UPS_NEXT_DAY_AIR = "UPS Next Day Air"
    UPS_WORLDWIDE_EXPRESS = "UPS Worldwide Express"
    UPS_WORLDWIDE_EXPEDITED = "UPS Worldwide Expedited"
    UPS_NEXT_DAY_AIR_EARLY = "UPS Next Day Air Early"
    UNKNOWN = "Unknown"


class OldShippingMethods(enum.Enum):
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
