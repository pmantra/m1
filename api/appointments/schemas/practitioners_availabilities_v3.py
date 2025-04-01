from __future__ import annotations

from marshmallow import fields

from views.schemas.base import (
    BooleanWithDefault,
    DataTimeWithDefaultV3,
    FloatWithDefaultV3,
    IntegerWithDefaultV3,
    ListWithDefaultV3,
    NestedWithDefaultV3,
    PaginableArgsSchemaV3,
    PaginableOutputSchemaV3,
    SchemaV3,
    StringWithDefaultV3,
)


class AvailabilitySchemaV3(SchemaV3):
    start_time = DataTimeWithDefaultV3()
    end_time = DataTimeWithDefaultV3()


class PractitionerAvailabilitiesDataSchemaV3(SchemaV3):
    availabilities = NestedWithDefaultV3(
        AvailabilitySchemaV3, many=True, dump_default=[]
    )
    duration = IntegerWithDefaultV3(dump_default=0)
    practitioner_id = IntegerWithDefaultV3(dump_default=0)
    product_id = IntegerWithDefaultV3(dump_default=0)
    product_price = FloatWithDefaultV3(dump_default=0.0)
    total_available_credits = IntegerWithDefaultV3(dump_default=0)


class PractitionersAvailabilitiesSchemaV3(PaginableOutputSchemaV3):
    data = NestedWithDefaultV3(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "NestedWithDefaultV3", base class "PaginableOutputSchemaV3" defined the type as "RawWithDefaultV3")
        PractitionerAvailabilitiesDataSchemaV3, many=True, dump_default=[]
    )


class PractitionersAvailabilitiesPostSchemaV3(PaginableArgsSchemaV3):
    practitioner_ids = ListWithDefaultV3(fields.Int(), dump_default=[])
    can_prescribe = BooleanWithDefault(dump_default=None)
    provider_type = StringWithDefaultV3(dump_default="")
    start_time = DataTimeWithDefaultV3()
    end_time = DataTimeWithDefaultV3()
    provider_steerage_sort = BooleanWithDefault(dump_default=None)
