from dataclasses import dataclass
from traceback import format_exc
from typing import Optional
from uuid import UUID

from jsonschema import ValidationError, validate

from utils.log import logger

log = logger(__name__)

FEEDBACK_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "uuid": {"type": "string", "format": "uuid"},
        "field_name": {"type": "string"},
        "updated_by": {"type": ["string", "null"]},
        "previous_value": {"type": "string"},
        "new_value": {"type": ["string", "null"]},
        "feedback_accepted": {"type": "boolean"},
    },
    "required": ["uuid", "field_name", "previous_value", "feedback_accepted"],
}

FEEDBACK_SCHEMA = {"type": "array", "items": FEEDBACK_ITEM_SCHEMA}

DOCUMENT_MAPPING_WITH_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "uuid": {"type": "string"},
        "extraction": {
            "type": "object",
            "properties": {
                "service_provider": {"type": ["string", "null"]},
                "patient_name": {"type": ["string", "null"]},
                "payment_amount": {"type": ["string", "null"]},
                "date_of_service": {
                    "type": ["string", "null"],
                    "anyOf": [
                        {"pattern": "^$"},
                        {"pattern": "^\d{4}-\d{2}-\d{2}$"},
                    ],
                },
                "service_evidence": {"type": ["boolean", "null"]},
            },
            "required": [
                "service_provider",
                "patient_name",
                "payment_amount",
                "date_of_service",
                "service_evidence",
            ],
        },
        "source_ids": {"type": "array"},
        "feedback": FEEDBACK_SCHEMA,
    },
    "required": ["uuid", "extraction", "source_ids"],
}

FEEDBACK_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "uuid": {"type": "string", "format": "uuid"},
        "field_name": {"type": "string"},
        "updated_by": {"type": ["string", "null"]},
        "previous_value": {"type": "string"},
        "new_value": {"type": ["string", "null"]},
        "feedback_accepted": {"type": "boolean"},
    },
    "required": ["uuid", "field_name", "previous_value", "feedback_accepted"],
}


@dataclass
class ReceiptExtractionDocumentMapping:
    document_mapping_uuid: UUID
    source_ids: list[int]
    service_provider: Optional[str]
    patient_name: Optional[str]
    payment_amount: Optional[int]
    date_of_service: Optional[str]
    service_evidence: Optional[bool]


@dataclass
class DocumentMappingFeedback:
    uuid: UUID
    field_name: str
    previous_value: str
    feedback_accepted: bool
    updated_by: Optional[str] = None
    new_value: Optional[str] = None


@dataclass
class ReceiptExtractionDocumentMappingWithFeedback:
    """
    Represents a document mapping with feedback.
    All extraction data is contained within the document_mapping field.
    """

    document_mapping: ReceiptExtractionDocumentMapping
    feedback: Optional[list[DocumentMappingFeedback]] = None


def _extract_document_mapping(
    extraction: dict, uuid: str, source_ids: list
) -> ReceiptExtractionDocumentMapping:
    """Helper function to create ReceiptExtractionDocumentMapping from validated data"""
    return ReceiptExtractionDocumentMapping(
        document_mapping_uuid=UUID(uuid),
        source_ids=[int(id_) for id_ in source_ids],
        service_provider=extraction.get("service_provider"),
        patient_name=extraction.get("patient_name"),
        payment_amount=int(extraction["payment_amount"])
        if extraction.get("payment_amount")
        else None,
        date_of_service=extraction.get("date_of_service"),
        service_evidence=extraction.get("service_evidence"),
    )


def _extract_feedback(feedback_dict: dict) -> DocumentMappingFeedback:
    """Helper function to create DocumentMappingFeedback from validated data"""
    return DocumentMappingFeedback(
        uuid=UUID(feedback_dict["uuid"]),
        field_name=feedback_dict["field_name"],
        previous_value=feedback_dict["previous_value"],
        feedback_accepted=feedback_dict["feedback_accepted"],
        updated_by=feedback_dict.get("updated_by"),
        new_value=feedback_dict.get("new_value"),
    )


def from_api_response_with_feedback(
    input_dict: dict,
) -> Optional[ReceiptExtractionDocumentMappingWithFeedback]:
    try:
        validate(instance=input_dict, schema=DOCUMENT_MAPPING_WITH_FEEDBACK_SCHEMA)

        # Create document mapping from top-level fields
        document_mapping = _extract_document_mapping(
            extraction=input_dict["extraction"],
            uuid=input_dict["uuid"],
            source_ids=input_dict["source_ids"],
        )

        # Parse feedback if it exists
        feedback = None
        if "feedback" in input_dict:
            feedback = [_extract_feedback(item) for item in input_dict["feedback"]]

        return ReceiptExtractionDocumentMappingWithFeedback(
            document_mapping=document_mapping,
            feedback=feedback,
        )

    except ValidationError as e:
        log.error(
            "JSONSchema validation error",
            document_mapping_uuid=input_dict.get("uuid"),
            reason=str(e),
        )
        return None
    except Exception:
        log.error(
            "Exception creating ReceiptExtractionDocumentMappingWithFeedback from response",
            document_mapping_uuid=input_dict.get("uuid"),
            reason=format_exc(),
        )
        return None


def from_api_response_feedback(input_dict: dict) -> Optional[DocumentMappingFeedback]:
    """Validates against FEEDBACK_ITEM_SCHEMA and returns feedback object"""
    try:
        validate(instance=input_dict, schema=FEEDBACK_ITEM_SCHEMA)
        return _extract_feedback(input_dict)
    except ValidationError as e:
        log.error(
            "JSONSchema validation error",
            feedback_uuid=input_dict.get("uuid"),
            reason=str(e),
        )
        return None
    except Exception:
        log.error(
            "Exception creating DocumentMappingFeedback from response",
            feedback_uuid=input_dict.get("uuid"),
            reason=format_exc(),
        )
        return None
