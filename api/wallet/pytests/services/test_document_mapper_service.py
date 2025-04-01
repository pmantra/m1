from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from requests import Response

from common.document_mapper.models import (
    DocumentMappingFeedback,
    ReceiptExtractionDocumentMappingWithFeedback,
)
from wallet.services.document_mapper_service import DocumentMapperService


@pytest.fixture
def mock_response():
    with patch(
        "common.base_triforce_client.BaseTriforceClient.make_service_request"
    ) as mock_request:
        mock_resp = Mock(spec=Response)
        mock_request.return_value = mock_resp
        yield mock_resp


@pytest.fixture
def service():
    return DocumentMapperService()


def test_map_documents_success(service, mock_response):
    source_ids = [1, 2, 3]
    service_provider = "Test Provider"
    service_category = "Fertility"
    amount = 1000
    date_of_service = datetime(2022, 6, 1)

    expected_uuid = uuid.uuid4()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "uuid": str(expected_uuid),
        "source_ids": source_ids,
        "extraction": {
            "service_provider": service_provider,
            "patient_name": "Test Patient",
            "payment_amount": "1000",
            "date_of_service": "2024-01-01",
            "service_evidence": True,
            "confidence_score": 0.95,
            "extracted_text": "Sample receipt text",
            "document_type": "receipt",
        },
    }

    result = service.map_documents(
        source_ids=source_ids,
        service_provider=service_provider,
        service_category=service_category,
        amount=amount,
        date_of_service=date_of_service,
        patient_name="Jane Smith",
    )

    assert mock_response.json.called, "Response json() was not called"
    assert isinstance(result, ReceiptExtractionDocumentMappingWithFeedback)
    assert str(result.document_mapping.document_mapping_uuid) == str(expected_uuid)
    assert result.document_mapping.source_ids == source_ids
    assert result.document_mapping.service_provider == service_provider
    assert result.document_mapping.patient_name == "Test Patient"
    assert result.document_mapping.payment_amount == 1000
    assert result.document_mapping.date_of_service == "2024-01-01"
    assert result.document_mapping.service_evidence is True


def test_map_documents_invalid_date_format(service, mock_response):
    source_ids = [1, 2, 3]
    service_provider = "Test Provider"
    service_category = "Fertility"
    amount = 1000
    date_of_service = datetime(2022, 6, 1)

    expected_uuid = uuid.uuid4()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "uuid": str(expected_uuid),
        "source_ids": source_ids,
        "extraction": {
            "service_provider": service_provider,
            "patient_name": "Test Patient",
            "payment_amount": 10000,
            "date_of_service": "01-01-2024",
            "service_evidence": True,
            "confidence_score": 0.95,
            "extracted_text": "Sample receipt text",
            "document_type": "receipt",
        },
    }

    result = service.map_documents(
        source_ids=source_ids,
        service_provider=service_provider,
        service_category=service_category,
        amount=amount,
        date_of_service=date_of_service,
        patient_name="Jane Smith",
    )

    assert result is None


def test_map_documents_api_error(service, mock_response):
    source_ids = [1]
    service_provider = "Test Provider"
    service_category = "Fertility"
    amount = 1000
    date_of_service = datetime(2022, 6, 1)

    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.json.side_effect = ValueError("Invalid JSON")

    result = service.map_documents(
        source_ids=source_ids,
        service_provider=service_provider,
        service_category=service_category,
        amount=amount,
        date_of_service=date_of_service,
        patient_name="Jane Smith",
    )

    assert result is None


def test_map_documents_invalid_response(service, mock_response):
    source_ids = [1]
    service_provider = "Test Provider"
    service_category = "Fertility"
    amount = 1000
    date_of_service = datetime(2022, 6, 1)

    mock_response.status_code = 200
    mock_response.json.return_value = {
        "uuid": str(uuid.uuid4()),
        "source_ids": source_ids,
    }

    result = service.map_documents(
        source_ids=source_ids,
        service_provider=service_provider,
        service_category=service_category,
        amount=amount,
        date_of_service=date_of_service,
        patient_name="Jane Smith",
    )

    assert result is None


def test_map_documents_missing_required_extraction_fields(service, mock_response):
    source_ids = [1]
    service_provider = "Test Provider"
    service_category = "Fertility"
    amount = 1000
    date_of_service = datetime(2022, 6, 1)

    mock_response.status_code = 200
    mock_response.json.return_value = {
        "uuid": str(uuid.uuid4()),
        "source_ids": source_ids,
        "extraction": {"some_other_field": "value"},
    }

    result = service.map_documents(
        source_ids=source_ids,
        service_provider=service_provider,
        service_category=service_category,
        amount=amount,
        date_of_service=date_of_service,
        patient_name="Jane Smith",
    )

    assert result is None


def test_map_documents_null_extraction_fields(service, mock_response):
    source_ids = [1]
    service_provider = "Test Provider"
    service_category = "Fertility"
    amount = 1000
    date_of_service = datetime(2022, 6, 1)

    mock_response.status_code = 200
    mock_response.json.return_value = {
        "uuid": str(uuid.uuid4()),
        "source_ids": source_ids,
        "extraction": {
            "service_provider": None,
            "patient_name": None,
            "payment_amount": None,
            "date_of_service": None,
            "service_evidence": None,
            "confidence_score": None,
            "extracted_text": None,
            "document_type": None,
        },
    }

    result = service.map_documents(
        source_ids=source_ids,
        service_provider=service_provider,
        service_category=service_category,
        amount=amount,
        date_of_service=date_of_service,
        patient_name="Jane Smith",
    )

    assert isinstance(result, ReceiptExtractionDocumentMappingWithFeedback)
    assert result.document_mapping.service_provider is None
    assert result.document_mapping.patient_name is None
    assert result.document_mapping.payment_amount is None
    assert result.document_mapping.date_of_service is None
    assert result.document_mapping.service_evidence is None


def test_format_request_body(service):
    source_ids = [1, 2, 3]
    service_provider = "Test Provider"
    service_category = "Fertility"
    amount = 1000
    date_of_service = datetime(2022, 6, 1)

    result = service.format_request_body(
        source_ids=source_ids,
        service_provider=service_provider,
        service_category=service_category,
        amount=amount,
        date_of_service=date_of_service,
        patient_name="Jane Smith",
    )

    assert result == {
        "service_provider": service_provider,
        "service_category": service_category,
        "source_ids": ["1", "2", "3"],
        "form_data": {
            "amount": "1000",
            "date_of_service": "2022-06-01",
            "patient_name": "Jane Smith",
        },
    }


def test_map_documents_missing_extraction_field(service, mock_response):
    source_ids = [1]
    service_provider = "Test Provider"
    service_category = "Fertility"
    amount = 1000
    date_of_service = datetime(2022, 6, 1)

    mock_response.status_code = 200
    mock_response.json.return_value = {
        "uuid": str(uuid.uuid4()),
        "source_ids": source_ids,
        "extraction": {
            "service_provider": "Test Provider",
            "patient_name": "Test Patient",
            # Missing payment_amount
            "date_of_service": "2024-01-01",
            "service_evidence": True,
        },
    }

    result = service.map_documents(
        source_ids=source_ids,
        service_provider=service_provider,
        service_category=service_category,
        amount=amount,
        date_of_service=date_of_service,
        patient_name="Jane Smith",
    )

    assert result is None


def test_map_documents_empty_extraction(service, mock_response):
    source_ids = [1]
    service_provider = "Test Provider"
    service_category = "Fertility"
    amount = 1000
    date_of_service = datetime(2022, 6, 1)

    mock_response.status_code = 200
    mock_response.json.return_value = {
        "uuid": str(uuid.uuid4()),
        "source_ids": source_ids,
        "extraction": {},
    }

    result = service.map_documents(
        source_ids=source_ids,
        service_provider=service_provider,
        service_category=service_category,
        amount=amount,
        date_of_service=date_of_service,
        patient_name="Jane Smith",
    )

    assert result is None


def test_map_documents_all_fields_null(service, mock_response):
    source_ids = [1]
    service_provider = "Test Provider"
    service_category = "Fertility"
    amount = 1000
    date_of_service = datetime(2022, 6, 1)

    mock_response.status_code = 200
    mock_response.json.return_value = {
        "uuid": str(uuid.uuid4()),
        "source_ids": source_ids,
        "extraction": {
            "service_provider": None,
            "patient_name": None,
            "payment_amount": None,
            "date_of_service": None,
            "service_evidence": None,
        },
    }

    result = service.map_documents(
        source_ids=source_ids,
        service_provider=service_provider,
        service_category=service_category,
        amount=amount,
        date_of_service=date_of_service,
        patient_name="Jane Smith",
    )

    assert isinstance(result, ReceiptExtractionDocumentMappingWithFeedback)
    assert result.document_mapping.service_provider is None
    assert result.document_mapping.patient_name is None
    assert result.document_mapping.payment_amount is None
    assert result.document_mapping.date_of_service is None
    assert result.document_mapping.service_evidence is None


def test_get_document_mapping_success(service, mock_response):
    expected_uuid = uuid.uuid4()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "uuid": str(expected_uuid),
        "source_ids": [1, 2, 3],
        "extraction": {
            "service_provider": "Test Provider",
            "patient_name": "Test Patient",
            "payment_amount": "10000",
            "date_of_service": "2024-01-01",
            "service_evidence": True,
            "confidence_score": 0.95,
            "extracted_text": "Sample receipt text",
            "document_type": "receipt",
        },
        "feedback": [
            {
                "uuid": str(uuid.uuid4()),
                "field_name": "service_provider",
                "previous_value": "Test Provider",
                "feedback_accepted": True,
                "updated_by": "test@maven.com",
                "new_value": "Updated Provider",
            }
        ],
    }

    result = service.get_document_mapping(
        document_mapping_uuid=expected_uuid,
    )

    assert mock_response.json.called, "Response json() was not called"
    assert isinstance(result, ReceiptExtractionDocumentMappingWithFeedback)
    assert str(result.document_mapping.document_mapping_uuid) == str(expected_uuid)
    assert len(result.feedback) == 1
    assert result.feedback[0].field_name == "service_provider"


def test_get_document_mapping_empty_strings(service, mock_response):
    expected_uuid = uuid.uuid4()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "uuid": str(expected_uuid),
        "source_ids": [1, 2, 3],
        "extraction": {
            "service_provider": "",
            "patient_name": "",
            "payment_amount": "",
            "date_of_service": "",
            "service_evidence": False,
            "confidence_score": 0.95,
        },
    }

    result = service.get_document_mapping(
        document_mapping_uuid=expected_uuid,
    )

    assert mock_response.json.called, "Response json() was not called"
    assert isinstance(result, ReceiptExtractionDocumentMappingWithFeedback)
    assert str(result.document_mapping.document_mapping_uuid) == str(expected_uuid)
    assert result.feedback is None


def test_create_feedback_success(service, mock_response):
    document_mapping_uuid = uuid.uuid4()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "uuid": str(uuid.uuid4()),
        "field_name": "service_provider",
        "previous_value": "Test Provider",
        "feedback_accepted": True,
        "updated_by": "test@maven.com",
        "new_value": "Updated Provider",
    }

    result = service.create_feedback(
        document_mapping_uuid=document_mapping_uuid,
        field_name="service_provider",
        updated_by="test@maven.com",
        previous_value="Test Provider",
        new_value="Updated Provider",
        feedback_accepted=True,
    )

    assert mock_response.json.called
    assert isinstance(result, DocumentMappingFeedback)
    assert result.field_name == "service_provider"
    assert result.previous_value == "Test Provider"
    assert result.new_value == "Updated Provider"
    assert result.feedback_accepted is True


def test_create_feedback_without_new_value(service, mock_response):
    document_mapping_uuid = uuid.uuid4()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "uuid": str(uuid.uuid4()),
        "field_name": "service_provider",
        "previous_value": "Test Provider",
        "feedback_accepted": False,
        "updated_by": "test@maven.com",
    }

    result = service.create_feedback(
        document_mapping_uuid=document_mapping_uuid,
        field_name="service_provider",
        updated_by="test@maven.com",
        previous_value="Test Provider",
        feedback_accepted=False,
    )

    assert mock_response.json.called
    assert isinstance(result, DocumentMappingFeedback)
    assert result.field_name == "service_provider"
    assert result.previous_value == "Test Provider"
    assert result.new_value is None
    assert result.feedback_accepted is False


def test_create_feedback_error(service, mock_response):
    document_mapping_uuid = uuid.uuid4()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    result = service.create_feedback(
        document_mapping_uuid=document_mapping_uuid,
        field_name="service_provider",
        updated_by="test@maven.com",
        previous_value="Test Provider",
    )

    assert result is None


def test_format_feedback_request_body(service):
    document_mapping_uuid = uuid.uuid4()

    result = service.format_feedback_request_body(
        document_mapping_uuid=document_mapping_uuid,
        field_name="service_provider",
        updated_by="test@maven.com",
        previous_value="Test Provider",
        new_value="Updated Provider",
        feedback_accepted=True,
    )

    assert result == {
        "document_mapping_uuid": str(document_mapping_uuid),
        "field_name": "service_provider",
        "updated_by": "test@maven.com",
        "previous_value": "Test Provider",
        "new_value": "Updated Provider",
        "feedback_accepted": True,
    }


def test_format_feedback_request_body_without_new_value(service):
    document_mapping_uuid = uuid.uuid4()

    result = service.format_feedback_request_body(
        document_mapping_uuid=document_mapping_uuid,
        field_name="service_provider",
        updated_by="test@maven.com",
        previous_value="Test Provider",
        feedback_accepted=False,
    )

    assert result == {
        "document_mapping_uuid": str(document_mapping_uuid),
        "field_name": "service_provider",
        "updated_by": "test@maven.com",
        "previous_value": "Test Provider",
        "feedback_accepted": False,
    }
