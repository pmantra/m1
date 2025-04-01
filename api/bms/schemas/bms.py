import datetime

import pytz
from marshmallow import Schema, ValidationError, fields, validate

from bms.constants import SHIPPING_BLACKOUT_DATES
from views.schemas.common import validate_phone_number
from views.schemas.common_v3 import V3AddressSchema, V3TelNumber, V3TelRegion

LATEST_WEEKDAY_ORDER_HOUR = 12
_MONDAY = 1
_SUNDAY = 7


class ProductSchema(Schema):
    name = fields.String(required=True, attribute="bms_product.name")
    quantity = fields.Integer(
        required=True,
        validate=[validate.Range(min=1, error="Value must be greater than 0")],
    )


class ShipmentSchema(Schema):
    __validators__ = [validate_phone_number(required=False)]
    recipient_name = fields.String(required=True)
    accommodation_name = fields.String(required=False)
    tracking_email = fields.Email(required=True)
    residential_address = fields.Boolean(required=False)
    friday_shipping = fields.Boolean(required=False)
    address = fields.Nested(V3AddressSchema, required=True)
    tel_number = V3TelNumber(required=True)
    tel_region = V3TelRegion()
    products = fields.Nested(ProductSchema, many=True, required=True)


class ReturnShipmentSchema(ShipmentSchema):
    products = fields.Nested(ProductSchema, many=True, required=False)


def validate_travel_start_date(data: datetime.date) -> None:
    arrival_date = data
    now_et = datetime.datetime.now() + pytz.timezone("America/New_York").utcoffset(
        datetime.datetime.utcnow()
    )

    _validate_shipment_cannot_arrive_on_a_holiday(arrival_date)
    _validate_travel_start_date_is_in_the_future(arrival_date, now_et)
    _validate_shipment_cannot_arrive_on_sunday(arrival_date)
    _validate_latest_order_time(arrival_date, now_et)


class BMSOrderSchema(Schema):
    id = fields.Integer()
    is_work_travel = fields.Boolean()
    travel_start_date = fields.Date(required=True, validate=validate_travel_start_date)
    travel_end_date = fields.Date()
    outbound_shipments = fields.Method("get_outbound_shipments")
    return_shipments = fields.Method("get_return_shipments")
    terms = fields.Dict(required=True)
    external_trip_id = fields.String(allow_none=True, default=None)

    def get_return_shipments(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return [
            {
                k: v
                for k, v in ShipmentSchema().dump(shipment).items()
                if k != "products"
            }
            for shipment in self.context["return_shipments"]
        ]

    def get_outbound_shipments(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return [
            {
                k: v
                for k, v in ShipmentSchema().dump(shipment).items()
                if k != "friday_shipping"
            }
            for shipment in self.context["outbound_shipments"]
        ]


class BMSOrderPostSchema(BMSOrderSchema):
    return_shipments = fields.Nested(ReturnShipmentSchema, many=True, required=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "BMSOrderSchema" defined the type as "Method")
    outbound_shipments = fields.Nested(ShipmentSchema, many=True, required=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "BMSOrderSchema" defined the type as "Method")


def _validate_shipment_cannot_arrive_on_a_holiday(arrival_date: datetime.date) -> None:
    if arrival_date in SHIPPING_BLACKOUT_DATES:
        raise ValidationError("Shipment cannot arrive on a holiday")


def _validate_travel_start_date_is_in_the_future(arrival_date: datetime.date, now_et) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if arrival_date <= now_et.date():
        raise ValidationError("Travel start date must be in the future")


def _validate_shipment_cannot_arrive_on_sunday(arrival_date: datetime.date) -> None:
    if arrival_date.isoweekday() == _SUNDAY:
        raise ValidationError(
            "We are unable to ship kits on a Sunday. Please choose a date before or "
            "after your actual arrival date for your kit to arrive."
        )


def _validate_latest_order_time(arrival_date, now_et):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    arrival_datetime = datetime.datetime(
        arrival_date.year, arrival_date.month, arrival_date.day
    )

    if arrival_date.isoweekday() == _MONDAY:
        latest_order_time = arrival_datetime.replace(
            hour=LATEST_WEEKDAY_ORDER_HOUR
        ) - datetime.timedelta(days=3)
    else:
        latest_order_time = arrival_datetime.replace(
            hour=LATEST_WEEKDAY_ORDER_HOUR
        ) - datetime.timedelta(days=1)

    if now_et >= latest_order_time:
        raise ValidationError("Past order cutoff time")
