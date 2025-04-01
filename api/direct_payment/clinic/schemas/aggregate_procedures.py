import enum
from typing import Any, List, Optional, TypeVar

from marshmallow import fields, validate

from direct_payment.clinic.schemas.procedures import FertilityClinicProceduresSchema
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.schemas.treatment_procedure import (
    TreatmentProcedureSchema,
)
from direct_payment.treatment_procedure.schemas.treatment_procedure_base_schema import (
    TreatmentProcedureBaseSchema,
)
from views.schemas.base import IntegerWithDefaultV3, PaginableArgsSchemaV3

T = TypeVar("T")


class FertilityClinicAggregateProcedureSchema(TreatmentProcedureBaseSchema):
    member_first_name = fields.String(required=True)
    member_last_name = fields.String(required=True)
    member_date_of_birth = fields.String(required=True)
    benefit_id = fields.String(required=True)
    benefit_type = fields.String(required=True)
    benefit_start_date = fields.String(required=True)
    benefit_expires_date = fields.String(required=True)
    wallet_state = fields.String(required=True)
    fertility_clinic_name = fields.String(required=True)
    fertility_clinic_location_name = fields.String(required=True)
    fertility_clinic_location_address = fields.String(required=True)
    global_procedure = fields.Nested(FertilityClinicProceduresSchema, required=False)
    partial_procedure = fields.Nested(
        TreatmentProcedureSchema(exclude=("partial_procedure", "global_procedure")),
        required=False,
    )


class AggregateProceduresSortByEnum(enum.Enum):
    MEMBER_LAST_NAME = "member_last_name"
    PROCEDURE_NAME = "procedure_name"
    CLINIC_NAME = "clinic_name"
    DATE = "date"
    COST = "cost"
    STATUS = "status"


class OrderDirectionsEnum(str, enum.Enum):
    ASC = "asc"
    DESC = "desc"


class AggregateProceduresFilterEnum(str, enum.Enum):
    CLINIC_LOCATION_ID = "clinic_location_id"
    CLINIC_ID = "clinic_id"
    STATUS = "status"


class MultiDictAwareList(fields.List):
    def _deserialize(
        self: "MultiDictAwareList",
        value: Any,
        attr: Optional[str],
        data: Any,
        **kw: Any,
    ) -> List[T]:
        if isinstance(data, dict) and hasattr(data, "getlist"):
            value = data.getlist(attr)
        return super()._deserialize(value, attr, data, **kw)


class FertilityClinicAggregateProceduresGetSchema(PaginableArgsSchemaV3):
    # todo: remove and allow to default to 10 once the frontend API call has been updated to include pagination query params
    limit = IntegerWithDefaultV3(
        dump_default=None,
        load_default=None,
    )
    sort_by = fields.String(
        validate=validate.OneOf([enum.value for enum in AggregateProceduresSortByEnum]),
        required=False,
    )
    status = MultiDictAwareList(
        fields.String(
            validate=validate.OneOf([enum.value for enum in TreatmentProcedureStatus]),
        ),
        required=False,
    )
    clinic_id = MultiDictAwareList(fields.Integer(), required=False)
    clinic_location_id = MultiDictAwareList(fields.Integer(), required=False)
