import datetime
import enum
from typing import Optional, Tuple

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.dialects.mysql import DOUBLE
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.sql import Select

from appointments.models.payments import MONEY_PRECISION
from models.base import TimeLoggedModelBase
from utils.data import JSONAlchemy


class CancellationReasons(enum.Enum):
    NOT_CANCELLED = "not_cancelled"
    NON_WORK_TRAVEL = "non_work_travel"
    WORK_TRIP_CANCELLED = "work_trip_cancelled"
    WORK_TRIP_RESCHEDULED = "work_trip_rescheduled"
    OTHER = "other"


class OrderStatus(enum.Enum):
    NEW = "NEW"
    PROCESSING = "PROCESSING"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"


class BMSOrder(TimeLoggedModelBase):
    __tablename__ = "bms_order"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    user = relationship("User")
    fulfilled_at = Column(DateTime)
    is_work_travel = Column(Boolean)
    is_maven_in_house_fulfillment = Column(Boolean, default=False, nullable=False)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.NEW.value)
    cancellation_reason = Column(
        Enum(CancellationReasons),
        nullable=False,
        default=CancellationReasons.NOT_CANCELLED.value,
    )
    travel_start_date = Column(Date)
    travel_end_date = Column(Date)
    terms = Column(JSONAlchemy(Text), default={})
    external_trip_id = Column(String(128))

    def __repr__(self) -> str:
        return f"<BMSOrder[{self.id}]: user={self.user}>"

    __str__ = __repr__

    def shipped_dates(self, reverse: bool = True) -> Tuple[datetime.datetime]:
        """Get the dates for all shipments which have occurred for this order."""
        gen = (x.shipped_at for x in self.shipments)
        # Default sort is ASC, so we only need to sort again for reversals.
        return (*sorted(gen, reverse=reverse),) if reverse else (*gen,)

    @hybrid_property
    def last_shipped_at(self) -> Optional[datetime.datetime]:
        """Get the latest shipment date for this order.

        Notes:
            `last_shipped_at` is what the user sees as the `return shipment date`.

            This is the user sending the kit to its destination.
        """
        dates = self.shipped_dates()
        return dates[0] if dates else None

    @last_shipped_at.expression  # type: ignore[no-redef] # Name "last_shipped_at" already defined on line 76
    def last_shipped_at(cls) -> Select:
        """Get the latest shipment date for this order (as a SQL expression).

        Notes:
            This is required for interop with Flask-Admin.

        See Also:
            - :py:class:`admin.app.BMSOrderView`
        """
        return (
            select([func.max(BMSShipment.shipped_at)])
            .where(BMSShipment.bms_order_id == cls.id)
            .label("last_shipped_at")
        )

    @hybrid_property
    def first_shipped_at(self) -> Optional[datetime.datetime]:
        """Get the first shipment date for this order.

        Notes:
            `first_shipped_at` is what the user sees as the `outbound shipment date`.

            This is us sending the kit to the user.
        """
        dates = self.shipped_dates(reverse=False)
        return dates[0] if dates else None

    @first_shipped_at.expression  # type: ignore[no-redef] # Name "first_shipped_at" already defined on line 104
    def first_shipped_at(cls) -> Select:
        """Get the latest shipment date for this order (as a SQL expression).

        Notes:
            This is required for interop with Flask-Admin.

        See Also:
            - :py:class:`admin.app.BMSOrderView`
        """
        return (
            select([func.min(BMSShipment.shipped_at)])
            .where(BMSShipment.bms_order_id == cls.id)
            .label("first_shipped_at")
        )


class ShippingMethods(enum.Enum):
    UPS_GROUND = "UPS Ground"
    UPS_3_DAY_SELECT = "UPS 3 Day Select"
    UPS_2_DAY = "UPS 2nd Day Air"
    UPS_1_DAY = "UPS 1 Day"
    UPS_NEXT_DAY_AIR = "UPS Next Day Air"
    UPS_WORLDWIDE_EXPRESS = "UPS Worldwide Express"
    UPS_WORLDWIDE_EXPEDITED = "UPS Worldwide Expedited"
    UPS_NEXT_DAY_AIR_EARLY = "UPS Next Day Air Early"
    UNKNOWN = "Unknown"

    @classmethod
    def has_value(cls, val: str) -> bool:
        return any(val == member.value for member in cls.__members__.values())


class BMSShipment(TimeLoggedModelBase):
    __tablename__ = "bms_shipment"
    __calculated_columns__ = frozenset(["shipping_method"])

    id = Column(Integer, primary_key=True)
    bms_order_id = Column(Integer, ForeignKey("bms_order.id"), nullable=False)
    bms_order = relationship("BMSOrder", backref="shipments")
    recipient_name = Column(String(255))
    residential_address = Column(Boolean)
    friday_shipping = Column(Boolean)
    shipped_at = Column(DateTime)
    tracking_numbers = Column(String(255))
    tracking_email = Column(String(255))
    accommodation_name = Column(String(255))
    tel_number = Column(String(100))
    tel_region = Column(String(10))
    cost = Column(DOUBLE(precision=MONEY_PRECISION, scale=2))
    address_id = Column(Integer, ForeignKey("address.id"), nullable=False)
    address = relationship("Address", backref="shipments")
    # Naming it _shipping_method causes it not to show up as a form field in admin :/
    shipment_method = Column("shipping_method", Enum(ShippingMethods), nullable=True)

    def __repr__(self) -> str:
        return f"<BMSShipment[{self.id}]: bms_order={self.bms_order}>"

    __str__ = __repr__

    @property
    def shipping_method(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.shipment_method and self.shipment_method.value  # type: ignore[attr-defined] # "str" has no attribute "value"


class BMSProduct(TimeLoggedModelBase):
    __tablename__ = "bms_product"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False, unique=True)
    description = Column(String(255))

    def __repr__(self) -> str:
        return f"<BMSProduct[{self.id}]: name={self.name}>"

    __str__ = __repr__


class BMSShipmentProducts(TimeLoggedModelBase):
    __tablename__ = "bms_shipment_products"
    constraints = (UniqueConstraint("bms_shipment_id", "bms_product_id"),)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Tuple[UniqueConstraint]", base class "ModelBase" defined the type as "Tuple[()]")  [assignment]

    id = Column(Integer, primary_key=True)
    bms_shipment_id = Column(Integer, ForeignKey("bms_shipment.id"))
    bms_shipment = relationship("BMSShipment", backref="products")
    bms_product_id = Column(Integer, ForeignKey("bms_product.id"))
    bms_product = relationship("BMSProduct")
    quantity = Column(Integer, nullable=False)

    def __repr__(self) -> str:
        return (
            "<BMSShipmentProducts: "
            f"bms_shipment={self.bms_shipment}, bms_product={self.bms_product}, quantity={self.quantity}>"
        )

    __str__ = __repr__
