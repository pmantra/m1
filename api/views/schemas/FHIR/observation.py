import enum

from marshmallow import Schema, fields, validate

from views.schemas.FHIR.common import (
    FHIRCodeableConceptSchema,
    FHIRIdentifierSchema,
    FHIRReferenceSchema,
)


class FHIRObservationStatusEnum(enum.Enum):
    registered = "registered"
    preliminary = "preliminary"
    final = "final"
    amended = "amended"
    corrected = "corrected"
    cancelled = "cancelled"
    entered_in_error = "entered-in-error"
    unknown = "unknown"


class FHIRObservationSchema(Schema):
    resourceType = fields.String()
    # id = fields.UUID()
    # meta = fields.Nested(FHIRResourceMetadataSchema)
    # language = fields.String(default="en-US")
    # text = fields.Nested(FHIRNarrativeSchema)
    extension = fields.List(fields.Raw())
    identifier = fields.List(fields.Nested(FHIRIdentifierSchema))
    # basedOn = fields.List(FHIRReferenceSchema)
    # partOf = fields.List(FHIRReferenceSchema)
    status = fields.String(
        validate=validate.OneOf([enum.value for enum in FHIRObservationStatusEnum])
    )
    # category
    code = fields.Nested(FHIRCodeableConceptSchema)
    subject = fields.Nested(FHIRReferenceSchema)
    # focus
    # encounter
    # effectiveDateTime
    # effectivePeriod
    # effectiveTiming
    # effectiveInstant
    issued = fields.DateTime()
    # performer = fields.List(FHIRReferenceSchema)
    # valueQuantity
    # valueCodeableConcept
    # valueString
    # valueBoolean
    # valueInteger
    # valueRange
    # valueRatio
    # valueSampledData
    # valueTime
    valueDateTime = fields.DateTime()
    # valuePeriod
    # dataAbsentReason
    # interpretation
    # note
    # bodySite
    # method
    # specimen
    # device
    # referenceRange
    # hasMember
    # derivedFrom
    # component
