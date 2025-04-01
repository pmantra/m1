from marshmallow import Schema, fields


class TreatmentProcedureBaseSchema(Schema):
    id = fields.Integer(required=True)
    uuid = fields.String(required=True)
    member_id = fields.Integer(required=True)
    infertility_diagnosis = fields.Method("get_infertility_diagnosis", required=False)
    global_procedure_id = fields.String(required=True)
    fertility_clinic_id = fields.Integer(required=True)
    fertility_clinic_location_id = fields.Integer(required=True)
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=False)
    procedure_name = fields.String(required=True)
    cost = fields.Integer(required=True)
    cost_credit = fields.Integer(required=False)
    status = fields.Method("get_procedure_status", required=True)

    def get_procedure_status(self, obj) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        return obj.status.value

    def get_infertility_diagnosis(self, obj) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        return obj.infertility_diagnosis.value if obj.infertility_diagnosis else None
