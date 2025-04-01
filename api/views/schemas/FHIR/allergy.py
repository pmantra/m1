from marshmallow import Schema, fields

from views.schemas.FHIR.common import (
    FHIRCodeableConceptSchema,
    FHIRIdentifierSchema,
    FHIRReferenceSchema,
)


class FHIRReactionSchema(Schema):
    # substance = fields.Nested(FHIRCodeableConceptSchema)
    # manifestation = fields.List(FHIRCodeableConceptSchema)
    description = fields.String()
    # onset = fields.DateTime()
    # severity = fields.Nested(FHIRCodingSchema)
    # exposureRoute = fields.Nested(FHIRCodeableConceptSchema)
    # note = fields.List(FHIRAnnotationSchema)


class FHIRAllergyIntoleranceSchema(Schema):
    """Allergies/adverse reactions associated with a patient."""

    resourceType = fields.Constant(constant="AllergyIntolerance")
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
    # type = fields.String()
    # category = fields.List(fields.String())
    # criticality = fields.String()
    # code = fields.Nested(FHIRCodeableConceptSchema)
    patient = fields.Nested(FHIRReferenceSchema)
    # encounter = fields.Nested(FHIRReferenceSchema)
    # onsetDateTime = fields.DateTime()
    # onsetAge = fields.Nested(FHIRQuantitySchema)
    # onsetPeriod = fields.Nested(FHIRPeriodSchema)
    # onsetRange = fields.Nested(FHIRRangeSchema)
    # onsetString = fields.String()
    recordedDate = fields.String()
    recorder = fields.Nested(FHIRReferenceSchema)
    # asserter = fields.Nested(FHIRReferenceSchema)
    # lastOccurrence = fields.DateTime()
    # note = fields.List(FHIRAnnotationSchema)
    reaction = fields.List(fields.Nested(FHIRReactionSchema))
