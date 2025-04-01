from unittest.mock import ANY, MagicMock, Mock, call, patch

import pytest

from utils.fhir_requests import FHIRClient
from utils.migrations.fhir.backfill_assessment_condition import (
    export_for_user,
    load_existing_data,
    run,
)


@pytest.fixture
def fhir_conditions():
    return [
        {
            "id": "condition-1",
            "identifier": [
                {"type": {"text": "user_id"}, "value": 1},
                {"type": {"text": "question_name"}, "value": "question-1"},
            ],
            "code": {"text": "question-1"},
            "recordedDate": "2021-11-01T00:00:00Z",
            "subject": {"identifier": {"value": 1}},
        },
        {
            "id": "condition-2",
            "identifier": [
                {"type": {"text": "user_id"}, "value": 1},
                {"type": {"text": "question_name"}, "value": "question-2"},
            ],
            "code": {"text": "question-2"},
            "recordedDate": "2021-11-01T00:00:00Z",
            "subject": {"identifier": {"value": 1}},
        },
    ]


@pytest.fixture
def other_user_fhir_conditions():
    return [
        {
            "id": "condition-3",
            "identifier": [
                {"type": {"text": "user_id"}, "value": 2},
                {"type": {"text": "question_name"}, "value": "question-3"},
            ],
            "code": {"text": "question-2"},
            "recordedDate": "2021-11-01T00:00:00Z",
            "subject": {"identifier": {"value": 2}},
        },
    ]


@patch(
    "utils.migrations.fhir.backfill_assessment_condition.export_for_user",
    return_value=1,
)
def test_script_triggers_export_per_user(mock_export_for_user):
    mock_users = [Mock(), Mock()]
    with patch(
        "utils.migrations.fhir.backfill_assessment_condition.get_users_with_data",
        return_value=mock_users,
    ), patch("utils.migrations.fhir.backfill_assessment_condition.FHIRClient"):
        run()
    mock_export_for_user.assert_has_calls(
        [
            call(ANY, ANY, mock_users[0], ANY, ANY, ANY, force=False),
            call(ANY, ANY, mock_users[1], ANY, ANY, ANY, force=False),
        ]
    )


def test_export_for_user_creates_batch(fhir_conditions):
    client = FHIRClient(use_batches=True)
    client.execute_batch = Mock()
    client.iterate_entries = MagicMock()
    client._single_request = Mock()

    with patch(
        "models.FHIR.condition.Condition.export_assessment_conditions",
        return_value=fhir_conditions,
    ):
        num_exported = export_for_user(
            exporter=Mock(),
            client=client,
            user=Mock(),
            questions=["question-1", "question-2"],
            start_date=None,
            stop_date=None,
            force=True,
        )

    assert num_exported == 2
    assert client.execute_batch.call_count == 1


def test_export_for_user_ignores_erroneous_user_results(
    fhir_conditions, other_user_fhir_conditions
):
    """Because it is possible for the FHIR system to find collision matches with
    the user id, verify that such an entry does not get processed to the cache.
    """
    client = FHIRClient(use_batches=True)
    client.iterate_entries = MagicMock(
        return_value=[
            {"resource": resource}
            for resource in (fhir_conditions + other_user_fhir_conditions)
        ]
    )

    with patch.object(client, "_single_request"):
        lookups = load_existing_data(
            client, user=Mock(id=1), questions=["question-1", "question-2"]
        )

    assert "question-3" not in lookups
    assert lookups.keys() == {"question-1", "question-2"}


def test_export_for_user_creates_missing(fhir_conditions):
    client = FHIRClient(use_batches=True)
    client.Condition = MagicMock()
    client.execute_batch = Mock()
    client.iterate_entries = MagicMock(
        # Pretend only one is on FHIR server
        return_value=[{"resource": fhir_conditions[0]}]
    )

    with patch(
        "models.FHIR.condition.Condition.export_assessment_conditions",
        return_value=fhir_conditions,
    ):
        num_exported = export_for_user(
            exporter=Mock(),
            client=client,
            user=Mock(id=1),
            questions=["question-1", "question-2"],
            start_date=None,
            stop_date=None,
        )

    # The one we left out of the FHIR response should get created.
    client.Condition.create.assert_called_once_with(fhir_conditions[1])
    # The one we kept should get skipped because the dates already match.
    client.Condition.update.assert_not_called()
    assert num_exported == 1


def test_export_for_user_updates_outdated(fhir_conditions):
    client = FHIRClient(use_batches=True)
    client.Condition = MagicMock()
    client.execute_batch = Mock()
    client.iterate_entries = MagicMock(
        # Pretend only one is on FHIR server
        return_value=[{"resource": fhir_conditions[0]}]
    )

    # Build a modified item newer than the FHIR data
    newer_item = dict(fhir_conditions[0], recordedDate="2021-11-02T00:00:00Z")

    with patch(
        "models.FHIR.condition.Condition.export_assessment_conditions",
        return_value=[newer_item],
    ):
        num_exported = export_for_user(
            exporter=Mock(),
            client=client,
            user=Mock(id=1),
            questions=["question-1", "question-2"],
            start_date=None,
            stop_date=None,
        )

    client.Condition.update.assert_called_once_with(newer_item["id"], newer_item)
    assert num_exported == 1
