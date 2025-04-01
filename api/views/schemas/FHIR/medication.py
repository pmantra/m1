import enum

from marshmallow import Schema, fields, validate

from views.schemas.FHIR.common import (
    FHIRAnnotationSchema,
    FHIRCodeableConceptSchema,
    FHIRIdentifierSchema,
    FHIRReferenceSchema,
    FHIRSimpleQuantitySchema,
)


class MedicationStatementStatusEnum(enum.Enum):
    active = "active"
    completed = "completed"
    entered_in_error = "entered-in-error"
    intended = "intended"
    stopped = "stopped"
    on_hold = "on-hold"
    unknown = "unknown"
    not_taken = "not-taken"


class FHIRTimingSchema(Schema):
    event = fields.List(fields.DateTime())
    # repeat = fields.Nested()
    code = fields.Nested(FHIRCodeableConceptSchema)


class FHIRDoseAndRateSchema(Schema):
    type = fields.Nested(FHIRCodeableConceptSchema)
    # doseRange = fields.Nested(FHIRRangeSchema)
    doseQuantity = fields.Nested(FHIRSimpleQuantitySchema)
    # rateRatio = fields.Nested(FHIRRatioSchema)
    # rateRange = fields.Nested(FHIRRangeSchema)
    rateQuantity = fields.Nested(FHIRSimpleQuantitySchema)


class FHIRDosageSchema(Schema):
    # extension
    # modifierExtension
    # sequence = fields.Integer()
    text = fields.String()
    # additionalInstruction = fields.List(FHIRCodeableConceptSchema)
    patientInstruction = fields.String()
    # timing = fields.Nested(FHIRTimingSchema)
    # asNeededBoolean = fields.Boolean()
    # asNeededCodeableConcept = fields.Nested(FHIRCodeableConceptSchema)
    # site = fields.Nested(FHIRCodeableConceptSchema)
    # route = fields.Nested(FHIRCodeableConceptSchema)
    # method = fields.Nested(FHIRCodeableConceptSchema)
    # doseAndRate = fields.List(fields.Nested(FHIRDoseAndRateSchema))
    # maxDosePerPeriod = fields.Nested(FHIRRatioSchema)
    # maxDosePerAdministration = fields.Nested(FHIRSimpleQuantitySchema)
    # maxDosePerLifetime = fields.Nested(FHIRSimpleQuantitySchema)


class FHIRMedicationStatementSchema(Schema):
    """A record of a medication that is being consumed by a patient."""

    resourceType = fields.Constant(constant="MedicationStatement")
    # id = fields.UUID()
    # meta = fields.Nested(FHIRResourceMetadataSchema)
    # implicitRules = fields.String()
    # language = fields.String(default="en-US")
    identifier = fields.List(fields.Nested(FHIRIdentifierSchema))
    # basedOn = fields.List(fields.Nested(FHIRReferenceSchema))
    # partOf = fields.List(fields.Nested(FHIRReferenceSchema))
    status = fields.String(
        validate=validate.OneOf([enum.value for enum in MedicationStatementStatusEnum])
    )
    # statusReason = fields.List(fields.String())
    # category = fields.Nested(FHIRCodeableConceptSchema)
    # medicationCodeableConcept = fields.Nested(FHIRCodeableConceptSchema)
    # medicationReference = fields.Nested(FHIRReferenceSchema)
    subject = fields.Nested(FHIRReferenceSchema)
    # context = fields.Nested(FHIRReferenceSchema)
    # effectiveDateTime = fields.DateTime()
    # effectivePeriod = fields.Nested(FHIRPeriodSchema)
    dateAsserted = fields.String()
    informationSource = fields.Nested(FHIRReferenceSchema)
    # derivedFrom = fields.List(fields.Nested(FHIRReferenceSchema))
    # reasonCode = fields.List(fields.Nested(FHIRCodeableConceptSchema))
    # reasonReference = fields.List(fields.Nested(FHIRReferenceSchema))
    note = fields.List(fields.Nested(FHIRAnnotationSchema))
    # dosage = fields.List(fields.Nested(FHIRDosageSchema))
