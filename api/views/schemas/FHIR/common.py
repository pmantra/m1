from __future__ import annotations

import enum

from marshmallow import Schema, fields, validate

import configuration
from models.base import TimeLoggedSnowflakeModelBase

# nonsense made-up url--we're waiting for trefolia-on-fhir for a real one
FLAGGED_EXTENSION_URL = "https://mavenclinic.com/fhir/StructureDefinition/flagged"
# NOTE: this declares all times to be UTC -- if the datetime has a timezone, use %z instead
FHIR_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def get_system_name() -> str:
    config = configuration.get_api_config()
    return config.common.base_url


class FHIRPeriodSchema(Schema):
    """A time period defined by a start and end date/time."""

    start = fields.DateTime()
    end = fields.DateTime()


class FHIRReferenceSchema(Schema):
    """A defined element in a resource which is a reference to another resource."""

    reference = fields.String()
    type = fields.String()
    # Note: the identifier field references a schema which references this schema. Using Raw to get around this.
    identifier = fields.Raw()
    display = fields.String()


def fhir_reference_from_model(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    model, representation: str | None = None, custom_type: str | None = None
) -> dict:
    """Auto-generate a standardized FHIR Reference from a maven monolith sqlalchemy model"""

    return {
        # reference will have a uri for FHIR resources, but is not a field for legacy references from maven models
        "type": custom_type if custom_type else model.__class__.__name__,
        "identifier": fhir_identifier_from_model(model),
        # TODO: abstract how to deal with the representation for front end -- add specific callable on models?
        "display": representation if representation else repr(model),
    }


def fhir_identifier_from_model(model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    system_name = get_system_name()
    return {
        "use": "official",
        # differentiate snowflake id or autoincrement id here
        "type": {
            "coding": None,
            "text": "Snowflake"
            if isinstance(model, TimeLoggedSnowflakeModelBase)
            else "Autoincrement",
        },
        "system": system_name,
        # will give an exception if the model does not have an id column-- and it should!
        "value": str(model.id),
        "period": None,
        "assigner": {"reference": system_name},
    }


class FHIRAnnotationSchema(Schema):
    """A text note which also contains information about who made the statement and when."""

    authorReference = fields.Nested(FHIRReferenceSchema)
    authorString = fields.String()
    time = fields.DateTime(format=FHIR_DATETIME_FORMAT)
    text = fields.String()


class FHIRCodingSchema(Schema):
    """Representation of a defined concept using a symbol from a defined "code system" """

    system = fields.String(default=get_system_name)
    version = fields.String()
    code = fields.String()
    display = fields.String()
    userSelected = fields.Boolean()


class FHIRCodeableConceptSchema(Schema):
    """
    A value that is usually supplied by providing a reference to one or more terminologies or ontologies,
    but may also be defined by the provision of text.
    """

    coding = fields.List(fields.Nested(FHIRCodingSchema))
    text = fields.String()


class FHIRIdentifierCodeEnum(enum.Enum):
    usual = "usual"
    official = "official"
    temp = "temp"
    secondary = "secondary"
    old = "old"


class FHIRIdentifierSchema(Schema):
    """
    A numeric or alphanumeric string that is associated with a single object or entity within a given system.
    Typically, identifiers are used to connect content in resources to external content.
    Identifiers are associated with objects and may be changed or retired due to human or system process and errors.
    """

    use = fields.String(
        default="official",
        validate=validate.OneOf([enum.value for enum in FHIRIdentifierCodeEnum]),
    )
    # Description of identifier
    type = fields.Nested(FHIRCodeableConceptSchema)
    # namespace for the identifier value
    system = fields.String(default=get_system_name)
    # unique value
    value = fields.String()
    # time where valid for use
    period = fields.Nested(FHIRPeriodSchema)
    # organization that issued the id -- can also be a string! How to represent this? custom field?
    assigner = fields.Nested(FHIRReferenceSchema)


class FHIRResourceMetadataSchema(Schema):
    """A set of metadata that provides technical and workflow context to the resource."""

    versionId = fields.UUID()
    lastUpdated = fields.DateTime()
    source = fields.String()
    profile = fields.String()
    security = fields.Nested(FHIRCodingSchema)
    tag = fields.Nested(FHIRCodingSchema)


class FHIRSimpleQuantitySchema(Schema):
    value = fields.Integer()
    unity = fields.String()
    system = fields.String(default=get_system_name)
    code = fields.String()


class FHIRQuantitySchema(FHIRSimpleQuantitySchema):
    comparator = fields.String()


class FHIRRangeItem(Schema):
    value = fields.Integer()
    unit = fields.String()


class FHIRRangeSchema(Schema):
    low = fields.Nested(FHIRRangeItem)
    high = fields.Nested(FHIRRangeItem)


class FHIRNarrativeSchema(Schema):
    status = fields.String()
    div = fields.String()


class FHIRRatioSchema(Schema):
    numerator = fields.Nested(FHIRQuantitySchema)
    denominator = fields.Nested(FHIRQuantitySchema)


class FHIRClinicalStatusEnum(enum.Enum):
    active = "active"
    recurrence = "recurrence"
    relapse = "relapse"
    inactive = "inactive"
    remission = "remission"
    resolved = "resolved"


class FHIRVerificationStatusEnum(enum.Enum):
    unconfirmed = "unconfirmed"
    provisional = "provisional"
    differential = "differential"
    confirmed = "confirmed"
    refuted = "refuted"
    entered_in_error = "entered-in-error"
