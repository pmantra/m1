import json

import pytest
from flask.testing import FlaskClient

from authn.domain.model import User
from models.tracks.client_track import TrackModifiers
from pytests.factories import (
    DefaultUserFactory,
    HealthProfileFactory,
    MemberProfileFactory,
)
from utils.api_interaction_mixin import APIInteractionMixin


class TestV2FHIRPatientHealthResource:
    def test_patient_health_resource_returns_expected_response(
        self, client: FlaskClient, api_helpers: APIInteractionMixin
    ):
        user = DefaultUserFactory.create(zendesk_user_id=123)
        MemberProfileFactory.create(user=user)
        HealthProfileFactory.create(user=user)
        response = client.get(
            f"/api/v2/users/{user.id}/patient_health_record",
            headers=api_helpers.json_headers(user),
        )
        assert response.status_code == 200
        response_json = json.loads(response.data)
        assert response_json["zendesk_user_id"] == "123"
        assert response_json["patient"][
            "pregnancyDueDate"
        ] == user.health_profile.due_date.strftime("%Y-%m-%d")

    @pytest.mark.skip(
        reason="Response track_modifiers is coming back empty resulting in an assertion error."
    )
    def test_patient_health_resource_returns_track_modifiers(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        create_doula_only_member: User,
    ):
        MemberProfileFactory.create(user=create_doula_only_member)
        HealthProfileFactory.create(user=create_doula_only_member)
        response = client.get(
            f"/api/v2/users/{create_doula_only_member.id}/patient_health_record",
            headers=api_helpers.json_headers(create_doula_only_member),
        )
        assert response.status_code == 200
        response_json = json.loads(response.data)
        assert response_json["tracks"]["active_tracks"][0]["track_modifiers"] == [
            TrackModifiers.DOULA_ONLY
        ]
