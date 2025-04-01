import json
from unittest.mock import MagicMock

import freezegun
import pytest
from flask.testing import FlaskClient

from authn.models.user import User
from common.health_profile.health_profile_service_models import (
    PregnancyAndRelatedConditions,
)
from utils.api_interaction_mixin import APIInteractionMixin


@pytest.fixture(scope="function")
def patch_current_pregnancy_and_related_conditions_request(
    default_user: User, modifier_dict: dict, ivf_dict: dict
) -> dict:
    return {
        "pregnancy": {
            "user_id": default_user.id,
            "estimated_date": "2025-05-10",
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
def patch_past_pregnancy_and_related_conditions_request(
    default_user: User,
    modifier_dict: dict,
    ivf_dict: dict,
) -> dict:
    return {
        "pregnancy": {
            "user_id": default_user.id,
            "abatement_date": "2024-01-01",
            "is_first_occurrence": True,
            "method_of_conception": ivf_dict,
            "outcome": {
                "value": "live birth - term",
                "modifier": modifier_dict,
                "updated_at": "2025-02-01T20:20:29",
            },
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


@pytest.fixture(scope="class", autouse=True)
@freezegun.freeze_time("2025-03-05 00:00:00")
def freeze_time():
    yield


@pytest.mark.usefixtures("freeze_time")
class TestPatchPregnancyAndRelatedConditions:
    @pytest.mark.parametrize(
        argnames="data",
        argvalues=[
            {},
            {"pregnancy": {}, "related_conditions": {}},
            {"pregnancy": {"estimated_date": "2025-01-01"}, "related_conditions": {}},
            {
                "pregnancy": {"abatement_date": "2025-06-10"},
                "related_conditions": {},
            },
            {
                "pregnancy": {
                    "estimated_date": "2025-01-01",
                    "outcome": {
                        "value": "stillbirth",
                    },
                },
                "related_conditions": {},
            },
        ],
        ids=[
            "empty_request",
            "no_user_id",
            "estimated_date_in_the_past",
            "abatement_date_in_the_future",
            "current_pregnancy_should_not_have_outcome",
        ],
    )
    def test_bad_request(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        data: dict,
        mock_migration_flag_dual_write,
    ):
        pregnancy_id = "123e4567-e89b-12d3-a456-426614174000"
        response = client.patch(
            f"/api/v1/pregnancy_and_related_conditions/{pregnancy_id}",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(data),
        )
        assert response.status_code == 400

    def test_patch_current_pregnancy_success(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        patch_current_pregnancy_and_related_conditions_request: dict,
        current_pregnancy_and_related_conditions_dict: dict,
        mock_tracks: MagicMock,
        mock_update_health_profile_in_braze: MagicMock,
        mock_member_risk_service: MagicMock,
        mock_hps_client: MagicMock,
        mock_migration_flag_dual_write,
    ):
        # Given
        mock_hps_client.patch_pregnancy_and_related_conditions.return_value = (
            PregnancyAndRelatedConditions.from_dict(
                current_pregnancy_and_related_conditions_dict
            )
        )

        # When
        pregnancy_id = "123e4567-e89b-12d3-a456-426614174000"
        patch_response = client.patch(
            f"/api/v1/pregnancy_and_related_conditions/{pregnancy_id}",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(patch_current_pregnancy_and_related_conditions_request),
        )

        # Then
        assert patch_response.status_code == 200
        assert patch_response.json == current_pregnancy_and_related_conditions_dict
        mock_tracks.on_health_profile_update.assert_called_once()
        mock_update_health_profile_in_braze.delay.assert_called_once()
        mock_member_risk_service.create_trimester_risk_flags.assert_not_called()

        # verify due_date and first_time_mom are saved in the user's health profile
        get_response = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert get_response.json["due_date"] == "2025-05-10"
        assert get_response.json["first_time_mom"] is False

    def test_patch_past_pregnancy_success(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        patch_past_pregnancy_and_related_conditions_request: dict,
        past_pregnancy_and_related_conditions_dict: dict,
        mock_tracks: MagicMock,
        mock_update_health_profile_in_braze: MagicMock,
        mock_member_risk_service: MagicMock,
        mock_hps_client: MagicMock,
        mock_migration_flag_dual_write,
    ):
        # Given
        if default_user.health_profile.json.get("due_date"):
            del default_user.health_profile.json["due_date"]
        if default_user.health_profile.json.get("first_time_mom"):
            del default_user.health_profile.json["first_time_mom"]
        mock_hps_client.patch_pregnancy_and_related_conditions.return_value = (
            PregnancyAndRelatedConditions.from_dict(
                past_pregnancy_and_related_conditions_dict
            )
        )

        # When
        pregnancy_id = "123e4567-e89b-12d3-a456-426614174000"
        patch_response = client.patch(
            f"/api/v1/pregnancy_and_related_conditions/{pregnancy_id}",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(patch_past_pregnancy_and_related_conditions_request),
        )

        # Then
        assert patch_response.status_code == 200
        assert patch_response.json == past_pregnancy_and_related_conditions_dict
        mock_tracks.assert_not_called()
        mock_update_health_profile_in_braze.assert_not_called()
        mock_member_risk_service.create_trimester_risk_flags.assert_not_called()

        # verify due_date and first_time_mom are saved in the user's health profile
        get_response = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert get_response.json.get("due_date") is None
        assert get_response.json.get("first_time_mom") is None
