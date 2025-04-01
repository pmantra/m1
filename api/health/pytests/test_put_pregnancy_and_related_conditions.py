import json
from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient

from authn.models.user import User
from common.health_profile.health_profile_service_models import (
    PregnancyAndRelatedConditions,
)
from health.models.health_profile import HealthProfile
from pytests import freezegun
from utils.api_interaction_mixin import APIInteractionMixin


class TestPutPregnancyAndRelatedConditions:
    @pytest.mark.parametrize(
        argnames="data",
        argvalues=[
            {},
            {"pregnancy": {}, "related_conditions": {}},
            {"pregnancy": {"status": "active"}, "related_conditions": {}},
            {
                "pregnancy": {"status": "active", "estimated_date": "2024-01-01"},
                "related_conditions": {},
            },
            {
                "pregnancy": {
                    "status": "active",
                    "estimated_date": "2024-01-01",
                    "outcome": {
                        "value": "miscarriage",
                    },
                },
                "related_conditions": {},
            },
            {
                "pregnancy": {
                    "condition_type": "resolved",
                    "abatement_date": "2026-01-01",
                },
                "related_conditions": {},
            },
        ],
        ids=[
            "empty_request",
            "pregnancy_no_status",
            "current_pregnancy_no_estimated_date",
            "current_pregnancy_estimated_date_in_the_past",
            "current_pregnancy_should_not_have_outcome",
            "past_pregnancy_abatement_date_in_the_past",
        ],
    )
    @freezegun.freeze_time("2025-01-29 00:17:10")
    def test_bad_request(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        data: dict,
        mock_migration_flag_dual_write,
    ):
        response = client.put(
            f"/api/v1/users/{default_user.id}/pregnancy_and_related_conditions",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(data),
        )
        assert response.status_code == 400

    def test_put_current_pregnancy_success_for_new_pregnancy(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        put_current_pregnancy_and_related_conditions_request: dict,
        current_pregnancy_and_related_conditions_dict: dict,
        mock_tracks: MagicMock,
        mock_update_health_profile_in_braze: MagicMock,
        mock_member_risk_service: MagicMock,
        mock_hps_client: MagicMock,
        mock_migration_flag_dual_write,
    ):
        # Given
        self._reset_due_date_and_first_time_mom(default_user.health_profile)
        mock_hps_client.put_pregnancy_and_related_conditions.return_value = (
            PregnancyAndRelatedConditions.from_dict(
                current_pregnancy_and_related_conditions_dict
            )
        )

        # When
        put_response = client.put(
            f"/api/v1/users/{default_user.id}/pregnancy_and_related_conditions",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(put_current_pregnancy_and_related_conditions_request),
        )

        # Then
        assert put_response.status_code == 200
        assert put_response.json == current_pregnancy_and_related_conditions_dict
        mock_tracks.on_health_profile_update.assert_called_once()
        mock_update_health_profile_in_braze.delay.assert_called_once()
        mock_member_risk_service.create_trimester_risk_flags.assert_called_once()

        # verify due_date and first_time_mom are saved in the user's health profile
        get_response = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert get_response.json["due_date"] == "2025-05-01"
        assert get_response.json["first_time_mom"] is False

    def test_put_current_pregnancy_success_for_existing_pregnancy(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        put_current_pregnancy_and_related_conditions_request: dict,
        current_pregnancy_and_related_conditions_dict: dict,
        mock_tracks: MagicMock,
        mock_update_health_profile_in_braze: MagicMock,
        mock_member_risk_service: MagicMock,
        mock_hps_client: MagicMock,
        mock_migration_flag_dual_write,
    ):
        # Given
        mock_hps_client.put_pregnancy_and_related_conditions.return_value = (
            PregnancyAndRelatedConditions.from_dict(
                current_pregnancy_and_related_conditions_dict
            )
        )

        # When
        put_response = client.put(
            f"/api/v1/users/{default_user.id}/pregnancy_and_related_conditions",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(put_current_pregnancy_and_related_conditions_request),
        )

        # Then
        assert put_response.status_code == 200
        assert put_response.json == current_pregnancy_and_related_conditions_dict
        mock_tracks.on_health_profile_update.assert_called_once()
        mock_update_health_profile_in_braze.delay.assert_called_once()
        mock_member_risk_service.create_trimester_risk_flags.assert_not_called()

        # verify due_date and first_time_mom are saved in the user's health profile
        get_response = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert get_response.json["due_date"] == "2025-05-01"
        assert get_response.json["first_time_mom"] is False

    def test_put_past_pregnancy_success(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        put_past_pregnancy_and_related_conditions_request: dict,
        past_pregnancy_and_related_conditions_dict: dict,
        mock_tracks: MagicMock,
        mock_update_health_profile_in_braze: MagicMock,
        mock_member_risk_service: MagicMock,
        mock_hps_client: MagicMock,
        mock_migration_flag_dual_write,
    ):
        # Given
        self._reset_due_date_and_first_time_mom(default_user.health_profile)
        mock_hps_client.put_pregnancy_and_related_conditions.return_value = (
            PregnancyAndRelatedConditions.from_dict(
                past_pregnancy_and_related_conditions_dict
            )
        )

        # When
        put_response = client.put(
            f"/api/v1/users/{default_user.id}/pregnancy_and_related_conditions",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(put_past_pregnancy_and_related_conditions_request),
        )

        # Then
        assert put_response.status_code == 200
        assert put_response.json == past_pregnancy_and_related_conditions_dict
        mock_tracks.assert_not_called()
        mock_update_health_profile_in_braze.assert_not_called()
        mock_member_risk_service.create_trimester_risk_flags.assert_not_called()

        # verify due_date and first_time_mom are null in the user's health profile
        get_response = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert get_response.json.get("due_date") is None
        assert get_response.json.get("first_time_mom") is None

    def test_hps_request_failure(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        mock_hps_client: MagicMock,
        put_current_pregnancy_and_related_conditions_request: dict,
        mock_migration_flag_dual_write,
    ):
        # Given
        mock_hps_client.put_pregnancy_and_related_conditions.side_effect = Exception()

        # When
        put_response = client.put(
            f"/api/v1/users/{default_user.id}/pregnancy_and_related_conditions",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(put_current_pregnancy_and_related_conditions_request),
        )

        # Then
        assert put_response.status_code == 500

        # verify due_date and first_time_mom writes are saved in the user's health profile
        get_response = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert get_response.json["due_date"] == "2025-05-01"
        assert get_response.json["first_time_mom"] is False

    def test_track_update_failure(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        mock_hps_client: MagicMock,
        put_current_pregnancy_and_related_conditions_request: dict,
        mock_tracks: MagicMock,
        mock_update_health_profile_in_braze: MagicMock,
        mock_member_risk_service: MagicMock,
        mock_migration_flag_dual_write,
    ):
        # Given
        self._reset_due_date_and_first_time_mom(default_user.health_profile)
        mock_tracks.on_health_profile_update.side_effect = Exception()

        # When
        put_response = client.put(
            f"/api/v1/users/{default_user.id}/pregnancy_and_related_conditions",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(put_current_pregnancy_and_related_conditions_request),
        )

        # Then
        assert put_response.status_code == 500
        mock_tracks.on_health_profile_update.assert_called_once()
        mock_update_health_profile_in_braze.delay.assert_not_called()
        mock_member_risk_service.create_trimester_risk_flags.assert_not_called()

        # verify due_date and first_time_mom are NOT saved in the user's health profile
        get_response = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert get_response.json.get("due_date") is None
        assert get_response.json.get("first_time_mom") is None

    def test_braze_update_failure(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        mock_hps_client: MagicMock,
        put_current_pregnancy_and_related_conditions_request: dict,
        current_pregnancy_and_related_conditions_dict: dict,
        mock_tracks: MagicMock,
        mock_update_health_profile_in_braze: MagicMock,
        mock_member_risk_service: MagicMock,
        mock_migration_flag_dual_write,
    ):
        # Given
        self._reset_due_date_and_first_time_mom(default_user.health_profile)
        mock_update_health_profile_in_braze.delay.side_effect = Exception()
        mock_hps_client.put_pregnancy_and_related_conditions.return_value = (
            PregnancyAndRelatedConditions.from_dict(
                current_pregnancy_and_related_conditions_dict
            )
        )

        # When
        put_response = client.put(
            f"/api/v1/users/{default_user.id}/pregnancy_and_related_conditions",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(put_current_pregnancy_and_related_conditions_request),
        )

        # Then
        assert put_response.status_code == 200
        assert put_response.json == current_pregnancy_and_related_conditions_dict
        mock_tracks.on_health_profile_update.assert_called_once()
        mock_update_health_profile_in_braze.delay.assert_called_once()
        mock_member_risk_service.create_trimester_risk_flags.assert_called_once()

        # verify due_date and first_time_mom are saved in the user's health profile
        get_response = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert get_response.json["due_date"] == "2025-05-01"
        assert get_response.json["first_time_mom"] is False

    def test_risk_flag_update_failure(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        mock_hps_client: MagicMock,
        put_current_pregnancy_and_related_conditions_request: dict,
        current_pregnancy_and_related_conditions_dict: dict,
        mock_tracks: MagicMock,
        mock_update_health_profile_in_braze: MagicMock,
        mock_member_risk_service: MagicMock,
        mock_migration_flag_dual_write,
    ):
        # Given
        self._reset_due_date_and_first_time_mom(default_user.health_profile)
        mock_member_risk_service.create_trimester_risk_flags.side_effect = Exception()
        mock_hps_client.put_pregnancy_and_related_conditions.return_value = (
            PregnancyAndRelatedConditions.from_dict(
                current_pregnancy_and_related_conditions_dict
            )
        )

        # When
        put_response = client.put(
            f"/api/v1/users/{default_user.id}/pregnancy_and_related_conditions",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(put_current_pregnancy_and_related_conditions_request),
        )

        # Then
        assert put_response.status_code == 200
        mock_tracks.on_health_profile_update.assert_called_once()
        mock_update_health_profile_in_braze.delay.assert_called_once()
        mock_member_risk_service.create_trimester_risk_flags.assert_called_once()

        # verify due_date and first_time_mom are saved in the user's health profile
        get_response = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert get_response.json["due_date"] == "2025-05-01"
        assert get_response.json["first_time_mom"] is False

    def test_internal_error_when_migration_flag_off(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        put_current_pregnancy_and_related_conditions_request: dict,
        mock_hps_client: MagicMock,
        mock_migration_flag_off,
    ):
        put_response = client.put(
            f"/api/v1/users/{default_user.id}/pregnancy_and_related_conditions",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(put_current_pregnancy_and_related_conditions_request),
        )
        assert put_response.status_code == 500

    def test_no_mono_update_when_migration_flag_complete(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        put_current_pregnancy_and_related_conditions_request: dict,
        current_pregnancy_and_related_conditions_dict: dict,
        mock_tracks: MagicMock,
        mock_update_health_profile_in_braze: MagicMock,
        mock_member_risk_service: MagicMock,
        mock_hps_client: MagicMock,
        mock_migration_flag_complete,
    ):
        # Given
        self._reset_due_date_and_first_time_mom(default_user.health_profile)
        mock_hps_client.put_pregnancy_and_related_conditions.return_value = (
            PregnancyAndRelatedConditions.from_dict(
                current_pregnancy_and_related_conditions_dict
            )
        )

        # When
        put_response = client.put(
            f"/api/v1/users/{default_user.id}/pregnancy_and_related_conditions",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(put_current_pregnancy_and_related_conditions_request),
        )

        # Then
        assert put_response.status_code == 200
        assert put_response.json == current_pregnancy_and_related_conditions_dict
        mock_tracks.on_health_profile_update.assert_not_called()
        mock_update_health_profile_in_braze.delay.assert_not_called()
        mock_member_risk_service.create_trimester_risk_flags.assert_not_called()

        # verify due_date and first_time_mom are NOT saved in the user's health profile
        get_response = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert get_response.json.get("due_date") is None
        assert get_response.json.get("first_time_mom") is None

    @staticmethod
    def _reset_due_date_and_first_time_mom(health_profile: HealthProfile):
        if health_profile.json.get("due_date"):
            del health_profile.json["due_date"]
        if health_profile.json.get("first_time_mom"):
            del health_profile.json["first_time_mom"]
