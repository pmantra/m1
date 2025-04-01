from unittest.mock import ANY, Mock, call, patch

import pytest
from google.auth.transport import requests as google_requests

from tasks.fhir import fhir_export
from utils.fhir_requests import FHIRActions


class TracebackEndsWith(str):
    def __eq__(self, other):
        return other.endswith(f"\n{self}\n")


@patch("tasks.fhir.FHIRClient")
def test_individual_export_posts_payload(fhir_client):
    """Test that `fhir_export` initializes and posts via `FHIRClient`."""
    fhir_export("Condition", {"meta": {}}, subject="foo")
    assert fhir_client.call_count == 1
    assert fhir_client.return_value.Condition.create.call_count == 1


@patch("tasks.fhir.FHIRClient.get_session")
@patch("utils.fhir_requests.fhir_audit")
def test_individual_export_records_request_exception(fhir_audit, get_session):
    """Check for audit recording of RequestException (raised as
    `google.auth.transport.requests.exceptions.TransportError`)
    during a request failure.
    """
    mock_session_ctx = get_session.return_value.__enter__.return_value
    mock_session_ctx.post.side_effect = google_requests.exceptions.TransportError(
        "it broke"
    )
    with pytest.raises(google_requests.exceptions.TransportError):
        fhir_export("Foo", {"meta": {}}, subject="foo")
    fhir_audit.assert_has_calls(
        [
            call(
                action_type=FHIRActions.export_request_failed,
                target=ANY,
                data={
                    "request_exception": TracebackEndsWith(
                        "google.auth.exceptions.TransportError: it broke"
                    ),
                    "resource": "Foo",
                },
            )
        ]
    )


@patch("tasks.fhir.FHIRClient.get_session")
@patch("utils.fhir_requests.fhir_audit")
def test_individual_export_records_operation_error(fhir_audit, get_session):
    """Check for audit recording of FHIR operational error results."""
    mock_session_ctx = get_session.return_value.__enter__.return_value
    mock_session_ctx.post.return_value = Mock(
        url="/fake-url",
        request=Mock(method="POST", body='{"fake": "request body"}'),
        status_code=400,
        json=Mock(return_value={"resourceType": "OperationOutcome", "issue": []}),
    )
    fhir_export("Foo", {"meta": {}}, subject="foo")
    fhir_audit.assert_has_calls(
        [
            call(
                action_type=FHIRActions.export_operation_failed,
                target="/fake-url",
                data={
                    "request": {"fake": "request body"},
                    "response": {"resourceType": "OperationOutcome", "issue": []},
                    "resource": "Foo",
                    "status_code": 400,
                },
            )
        ]
    )


@patch("tasks.fhir.FHIRClient.get_session")
@patch("utils.fhir_requests.fhir_audit")
def test_individual_export_records_success(fhir_audit, get_session):
    """Check for audit recording of FHIR operational success."""
    mock_session_ctx = get_session.return_value.__enter__.return_value
    mock_session_ctx.post.return_value = Mock(
        url="/fake-url",
        request=Mock(method="POST", body='{"fake": "request body"}'),
        json=Mock(return_value={"resourceType": "fake success"}),
        status_code=200,
    )
    fhir_export("Foo", {"meta": {}}, subject="foo")
    fhir_audit.assert_has_calls(
        [
            call(
                action_type=FHIRActions.export_succeeded,
                target="/fake-url",
                data={
                    "request": {"fake": "request body"},
                    "resource": "Foo",
                },
            )
        ]
    )
