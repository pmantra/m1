from marshmallow import Schema, fields


class FertilityClinicProceduresSchema(Schema):
    id = fields.String(required=True)
    name = fields.String(required=True)
    cost = fields.Integer()
    credits = fields.Integer(required=True)
    annual_limit = fields.Integer(required=True)
    is_partial = fields.Boolean(required=True)
    is_diagnostic = fields.Boolean(required=True)
    parent_procedure_ids = fields.List(fields.String())
    partial_procedures = fields.List(
        fields.Nested(lambda: FertilityClinicProceduresSchema())  # type: ignore[arg-type] # Argument 1 to "Nested" has incompatible type "Callable[[], FertilityClinicProceduresSchema]"; expected "Union[SchemaABC, type, str]"
    )
