import enum

from marshmallow import Schema, fields

from views.schemas.FHIR.common import (
    FHIRAnnotationSchema,
    FHIRCodeableConceptSchema,
    FHIRIdentifierSchema,
    FHIRReferenceSchema,
)


class FHIRClinicalStatusEnum(enum.Enum):
    active = "active"
    recurrence = "recurrence"
    relapse = "relapse"
    inactive = "inactive"
    remission = "remission"
    resolved = "resolved"


class FHIRStageSchema(Schema):
    # summary = fields.Nested(FHIRCodeableConceptSchema)
    assessment = fields.List(fields.Nested(FHIRReferenceSchema))
    # type = fields.Nested(FHIRCodeableConceptSchema)


class FHIREvidenceSchema(Schema):
    # code = fields.List(FHIRCodeableConceptSchema)
    detail = fields.List(fields.Nested(FHIRReferenceSchema))


class FHIRConditionSchema(Schema):
    """A clinical condition, problem, diagnosis, or other event or concept that has risen to a level of concern."""

    resourceType = fields.Constant(constant="Condition")
    # id = fields.UUID()
    # meta = fields.Nested(FHIRResourceMetadataSchema)
    # implicitRules = fields.String()
    # language = fields.String(default="en-US")
    # text = fields.Nested(FHIRNarrativeSchema)
    # contained = fields.Raw()
    extension = fields.List(fields.Raw())
    # modifierExtension
    identifier = fields.List(fields.Nested(FHIRIdentifierSchema))
    clinicalStatus = fields.Nested(FHIRCodeableConceptSchema)
    verificationStatus = fields.Nested(FHIRCodeableConceptSchema)
    category = fields.List(fields.Nested(FHIRCodeableConceptSchema))
    # severity = fields.Nested(FHIRCodeableConceptSchema)
    code = fields.Nested(FHIRCodeableConceptSchema)
    # bodySite = fields.List(FHIRCodeableConceptSchema)
    subject = fields.Nested(FHIRReferenceSchema(exclude=["reference"]))
    # encounter = fields.Nested(FHIRReferenceSchema)
    # onsetDateTime = fields.DateTime()
    # onsetAge = fields.Nested(FHIRQuantitySchema)
    # onsetPeriod = fields.Nested(FHIRPeriodSchema)
    # onsetRange = fields.Nested(FHIRRangeSchema)
    # onsetString = fields.String()
    # abatementDateTime = fields.DateTime()
    # abatementAge = fields.Nested(FHIRQuantitySchema)
    # abatementPeriod = fields.Nested(FHIRPeriodSchema)
    # abatementRange = fields.Nested(FHIRRangeSchema)
    # abatementString = fields.String()
    recordedDate = fields.String()
    recorder = fields.Nested(FHIRReferenceSchema(exclude=["reference"]))
    # asserter = fields.Nested(FHIRReferenceSchema)
    # stage = fields.List(FHIRStageSchema)
    # evidence = fields.List(FHIREvidenceSchema)
    note = fields.List(fields.Nested(FHIRAnnotationSchema))
