import re

from marshmallow import Schema, fields, validate

from views.schemas.FHIR.common import (
    FHIRCodeableConceptSchema,
    FHIRIdentifierSchema,
    FHIRPeriodSchema,
)

# http://hl7.org/fhir/R4/datatypes.html#date
DATE_REGEX = re.compile(
    r"([0-9]([0-9]([0-9][1-9]|[1-9]0)|[1-9]00)|[1-9]000)(-(0[1-9]|1[0-2])(-(0[1-9]|[1-2][0-9]|3[0-1]))?)?"
)


# http://hl7.org/fhir/R4/datatypes.html#HumanName
class FHIRNameSchema(Schema):
    # id = fields.UUID()
    family = fields.String(default=None, allow_none=True)
    given = fields.List(fields.String())
    use = fields.String(default=None, allow_none=True)
    prefix = fields.String(default=None, allow_none=True)
    suffix = fields.String(default=None, allow_none=True)
    period = fields.Nested(FHIRPeriodSchema, default=None, allow_none=True)


# http://hl7.org/fhir/R4/datatypes.html#ContactPoint
class FHIRContactPoint(Schema):
    system = fields.String()
    value = fields.String()
    use = fields.String(default=None, allow_none=True)
    rank = fields.Integer(default=None, allow_none=True)
    period = fields.Nested(FHIRPeriodSchema, default=None, allow_none=True)


# http://hl7.org/fhir/R4/datatypes.html#Address
class FHIRAddressSchema(Schema):
    # id = fields.UUID()
    line = fields.List(fields.String())
    city = fields.String()
    # district = fields.String()
    state = fields.String()
    postalCode = fields.String()
    use = fields.String(default=None, allow_none=True)
    # type = fields.String()
    # text = fields.String()
    period = fields.Nested(FHIRPeriodSchema, default=None, allow_none=True)
    extension = fields.List(fields.Raw())


# not yet in use
class FHIRCommunicationSchema(Schema):
    # id = fields.UUID()
    language = fields.Nested(FHIRCodeableConceptSchema)
    preferred = fields.Boolean()


# https://build.fhir.org/ig/HL7/US-Core-R4/StructureDefinition-us-core-patient.html
class FHIRPatientSchema(Schema):
    # id = fields.UUID()
    # meta = fields.Nested(FHIRResourceMetadataSchema)
    # implicitRules = fields.String()
    # language = fields.String(default="en-US")
    # text = fields.Nested(FHIRNarrativeSchema)
    # extension = fields.Nested(FHIRExtensionSchema, many=True)
    resourceType = fields.Constant(constant="Patient")
    identifier = fields.Nested(FHIRIdentifierSchema, many=True)
    name = fields.Nested(FHIRNameSchema, many=True)
    telecom = fields.Nested(FHIRContactPoint, many=True)
    # not fhir-compliant--oh well! :)
    gender = fields.String(default=None, allow_none=True)
    sexAtBirth = fields.String(default=None, allow_none=True)
    pronouns = fields.String(default=None, allow_none=True)
    address = fields.Nested(FHIRAddressSchema, many=True)
    birthDate = fields.String(validate=validate.Regexp(DATE_REGEX))
    active = fields.Boolean()
    fertilityTreatmentStatus = fields.String(default=None, allow_none=True)
    # contained = fields.Raw() # nested resources of any type...
    # maritalStatus = fields.Nested(FHIRCodeableConceptSchema)
    # photo = fields.Nested(FHIRAttachmentSchema, many=True)
    # contact = fields.Nested(FHIRContactSchema, many=True)
    communication = fields.Nested(FHIRCommunicationSchema, many=True)
    # link = fields.Nested(FHIRLinkSchema, many=True)
    extension = fields.List(
        fields.Raw()
    )  # unfortunately the data in here takes many shapes...
    pregnancyDueDate = fields.String(validate=validate.Regexp(DATE_REGEX))
