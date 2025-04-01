from flask import request
from marshmallow import Schema, fields

from common.global_procedures.procedure import ProcedureService
from direct_payment.clinic.schemas.procedures import FertilityClinicProceduresSchema
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from direct_payment.treatment_procedure.schemas.treatment_procedure_base_schema import (
    TreatmentProcedureBaseSchema,
)


class TreatmentProcedureSchema(TreatmentProcedureBaseSchema):
    partial_procedure = fields.Nested(
        lambda: TreatmentProcedureSchema(exclude=("partial_procedure",)), required=False  # type: ignore[arg-type] # Argument 1 to "Nested" has incompatible type "Callable[[], TreatmentProcedureSchema]"; expected "Union[SchemaABC, type, str]"
    )
    procedure_type = fields.Method("get_procedure_type", required=True)
    global_procedure = fields.Method("get_global_procedure", required=True)

    def get_procedure_type(self, obj: TreatmentProcedure) -> str:
        return obj.procedure_type.value  # type: ignore[attr-defined] # "str" has no attribute "value"

    def get_global_procedure(
        self, obj: TreatmentProcedure
    ) -> FertilityClinicProceduresSchema:
        procedure = ProcedureService().get_procedure_by_id(
            procedure_id=obj.global_procedure_id, headers=request.headers  # type: ignore[arg-type] # Argument "headers" to "get_procedure_by_id" of "ProcedureService" has incompatible type "EnvironHeaders"; expected "Optional[Mapping[str, str]]"
        )
        # TODO: needs procedure service error handling (move this http request OUT of the schema)
        schema = FertilityClinicProceduresSchema()
        return schema.dump(procedure)


class TreatmentProcedurePUTRequestSchema(Schema):
    start_date = fields.Date(required=False)
    end_date = fields.Date(required=False)
    status = fields.String(required=False)
    partial_global_procedure_id = fields.String(required=False)


class TreatmentProcedurePOSTRequestSchema(Schema):
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=False)
    member_id = fields.Integer(required=True)
    infertility_diagnosis = fields.String(required=False, allow_none=True)
    global_procedure_id = fields.String(required=True)
    fertility_clinic_id = fields.Integer(required=True)
    fertility_clinic_location_id = fields.Integer(required=True)


class TreatmentProceduresPOSTRequestSchema(Schema):
    procedures = fields.Nested(TreatmentProcedurePOSTRequestSchema, many=True)
