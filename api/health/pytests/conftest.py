from unittest import mock
from unittest.mock import MagicMock

import pytest
from ldclient import Stage


@pytest.fixture(scope="function")
def mock_migration_flag() -> MagicMock:
    with mock.patch(
        "health.resources.health_profile.migration_variation",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture(scope="function")
def mock_migration_flag_off(mock_migration_flag: MagicMock):
    mock_migration_flag.return_value = (Stage.OFF, None)


@pytest.fixture(scope="function")
def mock_migration_flag_dual_write(mock_migration_flag: MagicMock):
    mock_migration_flag.return_value = (Stage.DUALWRITE, None)


@pytest.fixture(scope="function")
def mock_migration_flag_complete(mock_migration_flag: MagicMock):
    mock_migration_flag.return_value = (Stage.COMPLETE, None)


@pytest.fixture(scope="function")
def mock_tracks() -> MagicMock:
    with mock.patch(
        "health.resources.health_profile.tracks",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture(scope="function")
def mock_update_health_profile_in_braze() -> MagicMock:
    with mock.patch(
        "health.resources.health_profile.update_health_profile_in_braze",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture(scope="function")
def mock_member_risk_service() -> MagicMock:
    with mock.patch(
        "health.services.member_risk_service.MemberRiskService",
        autospec=True,
        spec_set=True,
    ) as m:
        with mock.patch(
            "health.resources.health_profile.MemberRiskService",
            autospec=True,
            return_value=m,
        ):
            yield m


@pytest.fixture(scope="function")
def mock_health_profile_service() -> MagicMock:
    with mock.patch(
        "health.services.health_profile_service.HealthProfileService",
        autospec=True,
        spec_set=True,
    ) as m:
        with mock.patch(
            "health.resources.health_profile.HealthProfileService",
            autospec=True,
            return_value=m,
        ):
            yield m


@pytest.fixture(scope="function")
def mock_hps_client() -> MagicMock:
    with mock.patch(
        "common.health_profile.health_profile_service_client.HealthProfileServiceClient",
        autospec=True,
        spec_set=True,
    ) as m:
        with mock.patch(
            "health.resources.health_profile.HealthProfileServiceClient",
            autospec=True,
            return_value=m,
        ):
            yield m


@pytest.fixture(scope="function")
def modifier_dict() -> dict:
    return {
        "id": 123,
        "name": "Test provider",
        "role": "practitioner",
        "verticals": ["ob-gyn"],
    }


@pytest.fixture(scope="function")
def ivf_dict(modifier_dict: dict) -> dict:
    return {
        "value": "ivf",
        "modifier": modifier_dict,
        "updated_at": "2025-02-01T20:20:29",
    }


@pytest.fixture(scope="function")
def iui_dict(modifier_dict: dict) -> dict:
    return {
        "value": "iui",
        "modifier": modifier_dict,
        "updated_at": "2025-02-01T20:20:29",
    }


@pytest.fixture(scope="function")
def current_pregnancy_and_related_conditions_dict(
    modifier_dict: dict, ivf_dict: dict
) -> dict:
    return {
        "pregnancy": {
            "id": None,
            "condition_type": None,
            "status": "active",
            "onset_date": None,
            "abatement_date": None,
            "estimated_date": "2025-05-01",
            "is_first_occurrence": False,
            "method_of_conception": ivf_dict,
            "outcome": None,
            "modifier": modifier_dict,
            "created_at": "2025-02-01T20:20:29",
            "updated_at": "2025-02-01T20:20:29",
        },
        "related_conditions": {
            "gestational diabetes": {
                "id": None,
                "condition_type": None,
                "status": "Has gestational diabetes",
                "onset_date": "2025-02-01",
                "abatement_date": None,
                "estimated_date": None,
                "is_first_occurrence": None,
                "method_of_conception": None,
                "outcome": None,
                "modifier": modifier_dict,
                "created_at": "2025-02-01T20:20:29",
                "updated_at": "2025-02-01T20:20:29",
            },
        },
        "alerts": {},
    }


@pytest.fixture(scope="function")
def past_pregnancy_and_related_conditions_dict(
    modifier_dict: dict, iui_dict: dict
) -> dict:
    return {
        "pregnancy": {
            "id": None,
            "condition_type": None,
            "status": "resolved",
            "onset_date": None,
            "abatement_date": "2023-03-01",
            "estimated_date": None,
            "is_first_occurrence": True,
            "method_of_conception": iui_dict,
            "outcome": {
                "value": "live birth - term",
                "modifier": modifier_dict,
                "updated_at": "2025-02-01T20:20:29",
            },
            "modifier": modifier_dict,
            "created_at": "2025-02-01T20:20:29",
            "updated_at": "2025-02-01T20:20:29",
        },
        "related_conditions": {},
        "alerts": {},
    }


@pytest.fixture(scope="function")
def put_current_pregnancy_and_related_conditions_request(
    modifier_dict: dict, ivf_dict: dict
) -> dict:
    return {
        "pregnancy": {
            "status": "active",
            "estimated_date": "2025-05-01",
            "is_first_occurrence": False,
            "method_of_conception": ivf_dict,
            "modifier": modifier_dict,
        },
        "related_conditions": {
            "gestational diabetes": {
                "status": "Has gestational diabetes",
                "onset_date": "2025-02-01",
                "modifier": modifier_dict,
            },
        },
    }


@pytest.fixture(scope="function")
def put_past_pregnancy_and_related_conditions_request(
    modifier_dict: dict, iui_dict: dict
) -> dict:
    return {
        "pregnancy": {
            "status": "resolved",
            "abatement_date": "2023-03-01",
            "is_first_occurrence": True,
            "method_of_conception": iui_dict,
            "outcome": {
                "value": "live birth - term",
                "modifier": modifier_dict,
                "updated_at": "2025-02-01T20:20:29",
            },
            "modifier": modifier_dict,
        },
        "related_conditions": {},
    }
