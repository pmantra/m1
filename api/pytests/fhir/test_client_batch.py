from unittest.mock import ANY, Mock, call, patch

import pytest

from utils.fhir_requests import FHIRClient


@pytest.fixture
def batch_response():
    return {
        "type": "batch-response",
        "entry": [
            {
                "resource": {"resourceType": "Foo"},
                "response": {"status": "200 something"},
            },
            {
                "resource": {"resourceType": "Bar"},
                "response": {"status": "201 something"},
            },
            {
                "resource": {"resourceType": "OperationOutcome"},
                "response": {"status": "400 something"},
            },
        ],
    }


@patch("utils.fhir_requests.FHIRClient._single_request")
def test_use_batches_buffers_requests(_single_request):
    client = FHIRClient(use_batches=True)

    client.get("Foo")
    client.post("Foo", data={"foo": "bar"})
    client.put("Foo/123", data={"baz": "qux"})
    client.patch("Foo/456", data={"bar": "foo"})
    client.delete("Foo/789")

    _single_request.assert_not_called()

    expected_payloads = [
        {"request": {"method": "GET", "url": "Foo"}},
        {"request": {"method": "POST", "url": "Foo"}, "resource": {"foo": "bar"}},
        {"request": {"method": "PUT", "url": "Foo/123"}, "resource": {"baz": "qux"}},
        {"request": {"method": "PATCH", "url": "Foo/456"}, "resource": {"bar": "foo"}},
        {"request": {"method": "DELETE", "url": "Foo/789"}},
    ]
    assert client._batch_requests == expected_payloads


@patch("utils.fhir_requests.FHIRClient._single_request")
def test_use_batches_sends_single_request_on_execute(_single_request, fake_base_url):
    client = FHIRClient(use_batches=True)

    client.post("Foo", data={"foo": "bar"})
    client.put("Foo/123", data={"baz": "qux"})

    client.execute_batch()

    _single_request.assert_called_with(
        resource=None,
        method="POST",
        url=fake_base_url,
        data={
            "resourceType": "Bundle",
            "id": ANY,
            "meta": {
                "lastUpdated": ANY,
            },
            "type": "batch",
            "entry": [
                {
                    "request": {"method": "POST", "url": "Foo"},
                    "resource": {"foo": "bar"},
                },
                {
                    "request": {"method": "PUT", "url": "Foo/123"},
                    "resource": {"baz": "qux"},
                },
            ],
        },
    )


@patch("utils.fhir_requests.FHIRClient._single_request")
def test_use_batches_resets_queue_on_execute(_single_request):
    client = FHIRClient(use_batches=True)

    client.post("Foo", data={"foo": "bar"})
    client.put("Foo/123", data={"baz": "qux"})

    assert len(client._batch_requests) == 2
    client.execute_batch()
    assert client._batch_requests == []


def test_no_use_batches_disables_batch_workflow():
    client = FHIRClient()

    with pytest.raises(ValueError) as excinfo1:
        client._add_batch_request("Foo", method="PUT", data={"foo": "bar"})
    assert str(excinfo1.value) == "Batch execution was not configured for this client."

    with pytest.raises(ValueError) as excinfo2:
        client.execute_batch()
    assert str(excinfo2.value) == "Batch execution was not configured for this client."


def test_use_batches_respects_exempt_resources():
    client = FHIRClient(use_batches=True)
    client._single_request = Mock()
    client._add_batch_request = Mock()

    client.search(a=1, b=2)
    client.FakeResource.search(a=1, b=2)
    client._request("POST", resource="Foo", force=True)
    client._request("GET", resource="Bar", force=True)
    client._request("GET", resource="Baz")

    client._single_request.assert_has_calls(
        [
            call("_search", "POST", ANY, ANY),
            call("FakeResource/_search", "POST", ANY, ANY),
            call("Foo", "POST", ANY, ANY),
            call("Bar", "GET", ANY, ANY),
        ]
    )
    client._add_batch_request.assert_has_calls(
        [
            call("Baz", "GET", ANY),
        ]
    )


@patch("utils.fhir_requests.fhir_audit")
def test_batch_response_handler(mock_fhir_audit, batch_response):
    client = FHIRClient(use_batches=True)

    client.handle_response(
        Mock(
            json=Mock(return_value=batch_response),
            request=Mock(body={}, method="POST"),
            status_code=200,
        ),
        resources=["Foo", "Bar", "Baz"],
    )
    mock_fhir_audit.assert_has_calls(
        [
            call(
                action_type="export_succeeded",
                target=ANY,
                data={"resource": "Foo", "request": ANY},
            ),
            call(
                action_type="export_succeeded",
                target=ANY,
                data={"resource": "Bar", "request": ANY},
            ),
            call(
                action_type="export_operation_failed",
                target=ANY,
                data={
                    "resource": "Baz",
                    "request": ANY,
                    "response": ANY,
                    "status_code": 400,
                },
            ),
        ]
    )
