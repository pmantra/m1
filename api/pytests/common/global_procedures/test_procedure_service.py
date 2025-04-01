import copy
import datetime
import json
from unittest.mock import patch

import pytest
from requests import Response

from common.global_procedures.procedure import ProcedureService, unmarshal_procedure
from pytests.common.global_procedures import factories


@pytest.fixture
def create_mock_response():
    def return_response(content):
        mock_response = Response()
        mock_response.status_code = 200
        mock_response.encoding = "application/json"
        mock_response._content = json.dumps(content).encode("utf-8")
        return mock_response

    return return_response


def test_get_procedure_by_id(create_mock_response):
    # Given
    given_procedure = factories.GlobalProcedureFactory.create()
    given_procedure_id = given_procedure["id"]
    # When
    with patch.object(
        ProcedureService,
        "make_service_request",
        return_value=create_mock_response(given_procedure),
    ):
        service = ProcedureService()
        result = service.get_procedure_by_id(procedure_id=given_procedure_id)
        received_procedure_id = result["id"]
    # Then
    assert received_procedure_id == given_procedure_id


def test_get_procedures_by_id(create_mock_response):
    # Given
    given_procedures = factories.GlobalProcedureFactory.create_batch(size=2)
    given_procedure_ids = {gp["id"] for gp in given_procedures}
    # When
    with patch.object(
        ProcedureService,
        "make_service_request",
        return_value=create_mock_response({"results": given_procedures}),
    ):
        service = ProcedureService()
        result = service.get_procedures_by_ids(procedure_ids=[*given_procedure_ids])
        received_procedure_ids = {gp["id"] for gp in result}
    # Then
    assert received_procedure_ids == given_procedure_ids


def test_get_procedures_by_names_valid_date(create_mock_response):
    # Given
    given_procedures = factories.GlobalProcedureFactory.create_batch(size=2)
    given_procedure_names = {gp["name"] for gp in given_procedures}
    # When
    with patch.object(
        ProcedureService,
        "make_service_request",
        return_value=create_mock_response({"results": given_procedures}),
    ):
        service = ProcedureService()
        result = service.get_procedures_by_names(
            procedure_names=[*given_procedure_names],
            start_date=datetime.date(2023, 1, 1),
            end_date=datetime.date(2024, 1, 1),
        )
        received_procedure_names = {gp["name"] for gp in result}
    # Then
    assert received_procedure_names == given_procedure_names


def test_get_procedures_by_ndc_numbers(create_mock_response):
    # Given
    given_procedures = factories.GlobalProcedureFactory.create_batch(size=2)
    given_procedure_numbers = {gp["ndc_number"] for gp in given_procedures}
    # When
    with patch.object(
        ProcedureService,
        "make_service_request",
        return_value=create_mock_response({"results": given_procedures}),
    ):
        service = ProcedureService()
        result = service.get_procedures_by_ndc_numbers(
            ndc_numbers=[*given_procedure_numbers],
            start_date=datetime.date(2023, 1, 1),
            end_date=datetime.date(2024, 1, 1),
        )
        received_procedure_names = {gp["ndc_number"] for gp in result}
    # Then
    assert received_procedure_names == given_procedure_numbers


def test_get_all_procedures(create_mock_response):
    # Given
    given_global_procedures = factories.GlobalProcedureFactory.create_batch(size=2)
    given_partial_procedures = factories.PartialProcedureFactory.create_batch(size=2)
    given_procedures = given_global_procedures + given_partial_procedures
    expected_procedure_ids = {gp["id"] for gp in given_procedures}
    # When
    with patch.object(
        ProcedureService,
        "make_service_request",
        return_value=create_mock_response(given_procedures),
    ):
        service = ProcedureService()
        result = service.list_all_procedures()
        received_procedure_ids = {gp["id"] for gp in result}
    # Then
    assert received_procedure_ids == expected_procedure_ids


def test_create_global_procedure(create_mock_response):
    # Given
    given_procedure = factories.GlobalProcedureFactory.create(
        type="pharmacy", credits=0
    )
    given_procedure_id = given_procedure["id"]
    # When
    with patch.object(
        ProcedureService,
        "make_service_request",
        return_value=create_mock_response(given_procedure),
    ):
        service = ProcedureService()
        result = service.create_global_procedure(global_procedure=given_procedure)
        received_procedure_id = result["id"]
    # Then
    assert received_procedure_id == given_procedure_id


def test_create_global_procedure_fails(create_mock_response):
    # Given
    procedure_error = {
        "detail": "The indicated resource could not be found.",
        "title": "Not Found",
        "status": 404,
    }
    mock_response = create_mock_response(procedure_error)
    mock_response.status_code = 404
    given_procedure = factories.GlobalProcedureFactory.create(
        type="pharmacy", credits=0
    )
    # When
    with patch.object(
        ProcedureService,
        "make_service_request",
        return_value=mock_response,
    ):
        service = ProcedureService()
        result = service.create_global_procedure(global_procedure=given_procedure)
    # Then
    assert result is None


def test_unmarshal_parent_procedure():
    # Given
    given_global_procedure = factories.GlobalProcedureFactory.create()

    expected_unmarshalled_procedure = copy.deepcopy(given_global_procedure)
    expected_unmarshalled_procedure.update(
        created_at=datetime.datetime.fromisoformat(
            expected_unmarshalled_procedure["created_at"]
        ),
        updated_at=datetime.datetime.fromisoformat(
            expected_unmarshalled_procedure["updated_at"]
        ),
    )
    for partial in expected_unmarshalled_procedure["partial_procedures"]:
        partial.update(
            created_at=datetime.datetime.fromisoformat(partial["created_at"]),
            updated_at=datetime.datetime.fromisoformat(partial["updated_at"]),
        )
    # When
    unmarhsalled_procedure = unmarshal_procedure(given_global_procedure)

    # Then
    assert unmarhsalled_procedure == expected_unmarshalled_procedure


def test_unmarshal_invalid_response():
    # Given
    given_response = {"unknown": "field"}
    expected_unmarshalled_procedure = None
    # When
    unmarshalled_procedure = unmarshal_procedure(given_response)
    # Then
    assert unmarshalled_procedure == expected_unmarshalled_procedure


def test_unmarshal_min_fields_defaults_partial():
    # Given
    given_procedure = factories.CoreProcedureFieldsFactory.create()
    expected_unmarshalled_procedure = {
        **given_procedure,
        "created_at": datetime.datetime.fromisoformat(given_procedure["created_at"]),
        "updated_at": datetime.datetime.fromisoformat(given_procedure["updated_at"]),
        "is_partial": True,
        "parent_procedure_ids": None,
    }
    # When
    unmarshalled_procedure = unmarshal_procedure(given_procedure)
    # Then
    assert unmarshalled_procedure == expected_unmarshalled_procedure
