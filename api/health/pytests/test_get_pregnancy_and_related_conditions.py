import copy
from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient
from ldclient import Stage

from authn.models.user import User
from common.health_profile.health_profile_service_models import (
    PregnancyAndRelatedConditions,
)
from utils.api_interaction_mixin import APIInteractionMixin


class TestGetPregnancyAndRelatedConditions:
    def test_500_error_response_when_migration_flag_is_off(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        mock_migration_flag_off,
    ):
        response = client.get(
            f"/api/v1/users/{default_user.id}/pregnancy_and_related_conditions",
            headers=api_helpers.json_headers(default_user),
        )
        assert response.status_code == 500

    @pytest.mark.parametrize(
        argnames="migration_stage", argvalues=(Stage.DUALWRITE, Stage.SHADOW)
    )
    def test_data_is_return_from_mono_when_hps_has_no_data(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        mock_hps_client: MagicMock,
        mock_migration_flag: MagicMock,
        migration_stage: Stage,
    ):
        # Given
        due_date_in_mono = default_user.health_profile.due_date
        mock_migration_flag.return_value = (migration_stage, None)
        mock_hps_client.get_pregnancy_and_related_conditions.return_value = []

        # When
        response = client.get(
            f"/api/v1/users/{default_user.id}/pregnancy_and_related_conditions",
            headers=api_helpers.json_headers(default_user),
        )

        # Then
        assert response.status_code == 200
        assert response.json == [
            {
                "pregnancy": {
                    "id": None,
                    "condition_type": "pregnancy",
                    "status": "active",
                    "onset_date": None,
                    "abatement_date": None,
                    "estimated_date": due_date_in_mono.isoformat(),
                    "is_first_occurrence": None,
                    "method_of_conception": None,
                    "outcome": None,
                    "modifier": None,
                    "created_at": None,
                    "updated_at": None,
                },
                "related_conditions": {},
                "alerts": {},
            }
        ]

    @pytest.mark.parametrize(
        argnames="migration_stage", argvalues=(Stage.DUALWRITE, Stage.SHADOW)
    )
    def test_data_is_return_from_both_mono_and_hps(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        mock_hps_client: MagicMock,
        current_pregnancy_and_related_conditions_dict: dict,
        past_pregnancy_and_related_conditions_dict: dict,
        mock_migration_flag: MagicMock,
        migration_stage: Stage,
    ):
        # Given
        due_date_in_mono = default_user.health_profile.due_date
        mock_migration_flag.return_value = (migration_stage, None)
        mock_hps_client.get_pregnancy_and_related_conditions.return_value = [
            PregnancyAndRelatedConditions.from_dict(
                current_pregnancy_and_related_conditions_dict
            ),
            PregnancyAndRelatedConditions.from_dict(
                past_pregnancy_and_related_conditions_dict
            ),
        ]

        # When
        response = client.get(
            f"/api/v1/users/{default_user.id}/pregnancy_and_related_conditions",
            headers=api_helpers.json_headers(default_user),
        )

        # Then
        assert response.status_code == 200

        # due_date and first_time_mom should come from mono for the current pregnancy
        expected = copy.deepcopy(current_pregnancy_and_related_conditions_dict)
        expected["pregnancy"]["estimated_date"] = due_date_in_mono.isoformat()
        assert response.json[0] == expected

        # past pregnancy should stay the same as the HPS response
        assert response.json[1] == past_pregnancy_and_related_conditions_dict

    @pytest.mark.parametrize(
        argnames="migration_stage",
        argvalues=(Stage.LIVE, Stage.RAMPDOWN, Stage.COMPLETE),
    )
    def test_data_is_return_from_hps_only(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        default_user: User,
        mock_hps_client: MagicMock,
        current_pregnancy_and_related_conditions_dict: dict,
        past_pregnancy_and_related_conditions_dict: dict,
        mock_migration_flag: MagicMock,
        migration_stage: Stage,
    ):
        # Given
        mock_migration_flag.return_value = (migration_stage, None)
        mock_hps_client.get_pregnancy_and_related_conditions.return_value = [
            PregnancyAndRelatedConditions.from_dict(
                current_pregnancy_and_related_conditions_dict
            ),
            PregnancyAndRelatedConditions.from_dict(
                past_pregnancy_and_related_conditions_dict
            ),
        ]

        # When
        response = client.get(
            f"/api/v1/users/{default_user.id}/pregnancy_and_related_conditions",
            headers=api_helpers.json_headers(default_user),
        )

        # Then
        assert response.status_code == 200

        # all data should come from HPS
        assert response.json == [
            current_pregnancy_and_related_conditions_dict,
            past_pregnancy_and_related_conditions_dict,
        ]
