import datetime
import json
from unittest import mock

import pytest
from maven.feature_flags import test_data

from eligibility.pytests import factories as e9y_factories
from eligibility.pytests.factories import VerificationFactory
from models.tracks import TrackLifecycleError, TrackName, initiate_transition
from models.tracks.track import TRACK_CONFIG_L10N
from pytests import freezegun
from storage.connection import db


@pytest.fixture
def mock_fertility_track_eligible_user(factories):
    user = factories.EnterpriseUserFactory(
        tracks__name=TrackName.FERTILITY,
        enabled_tracks=[TrackName.FERTILITY],
    )
    return user


class TestStartTransition:
    def test_start_transition(self, client, api_helpers, factories):
        user = factories.EnterpriseUserFactory(
            tracks__name=TrackName.PREGNANCY,
            enabled_tracks=[TrackName.PREGNANCY, TrackName.POSTPARTUM],
        )
        track = user.active_tracks[0]
        assert track.transitioning_to is None
        data = {"destination": TrackName.POSTPARTUM}
        res = client.post(
            f"/api/v1/tracks/{track.id}/start-transition",
            headers=api_helpers.json_headers(user),
            data=api_helpers.json_data(data),
        )
        assert res.status_code == 200
        assert track.transitioning_to is not None

    @mock.patch(
        "health.services.health_profile_service.HealthProfileServiceClient.post_fertility_status_history"
    )
    def test_start_transition_from_fertility_to_pregnancy(
        self, mock_post_fertility_status_history, client, api_helpers, factories
    ):
        user = factories.EnterpriseUserFactory(
            tracks__name=TrackName.FERTILITY,
            enabled_tracks=[TrackName.FERTILITY, TrackName.PREGNANCY],
        )
        track = user.active_tracks[0]
        assert track.transitioning_to is None
        data = {"destination": TrackName.PREGNANCY}
        client.post(
            f"/api/v1/tracks/{track.id}/start-transition",
            headers=api_helpers.json_headers(user),
            data=api_helpers.json_data(data),
        )
        mock_post_fertility_status_history.assert_called_once_with(
            "successful_pregnancy"
        )

    def test_start_transition_with_invalid_destination(
        self, client, api_helpers, factories
    ):
        user = factories.EnterpriseUserFactory(
            tracks__name=TrackName.PREGNANCY,
            enabled_tracks=[TrackName.PREGNANCY, TrackName.POSTPARTUM],
        )
        track = user.active_tracks[0]
        data = {"destination": "not_a_track_name"}
        res = client.post(
            f"/api/v1/tracks/{track.id}/start-transition",
            headers=api_helpers.json_headers(user),
            data=api_helpers.json_data(data),
        )
        assert res.status_code == 400
        assert track.transitioning_to is None

    def test_start_transition_with_invalid_track_id(
        self, client, api_helpers, factories
    ):
        user = factories.EnterpriseUserFactory(
            tracks__name=TrackName.PREGNANCY,
            enabled_tracks=[TrackName.PREGNANCY, TrackName.POSTPARTUM],
        )
        track = user.active_tracks[0]
        data = {"destination": "not_a_track_name"}
        res = client.post(
            f"/api/v1/tracks/{track.id+1}/start-transition",
            headers=api_helpers.json_headers(user),
            data=api_helpers.json_data(data),
        )
        assert res.status_code == 404
        assert track.transitioning_to is None

    def test_start_transition_with_non_eligible_track_with_message(
        self, client, api_helpers, mock_fertility_track_eligible_user
    ):
        user = mock_fertility_track_eligible_user
        track = user.active_tracks[0]
        data = {"destination": TrackName.PREGNANCY}
        res = client.post(
            f"/api/v1/tracks/{track.id}/start-transition",
            headers=api_helpers.json_headers(user),
            data=api_helpers.json_data(data),
        )

        assert {
            "status": 400,
            "title": "Bad Request",
            "detail": f"Organization {user.organization_v2.id} is not configured for Track '{TrackName.PREGNANCY}'.",
            "message": "Congratulations on your pregnancy! Message your Care Advocate to learn more about Maven’s "
            "maternity support.",
        } in res.json["errors"]
        assert track.transitioning_to is None

    @mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    )
    def test_start_transition_with_missing_verification_with_message(
        self, patch_get_verification_for_user, client, api_helpers, factories
    ):
        user = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.FERTILITY, enabled_tracks=[TrackName.PREGNANCY]
        )
        patch_get_verification_for_user.return_value = None

        track = user.active_tracks[0]
        data = {"destination": TrackName.PREGNANCY}
        res = client.post(
            f"/api/v1/tracks/{track.id}/start-transition",
            headers=api_helpers.json_headers(user),
            data=api_helpers.json_data(data),
        )

        assert {
            "status": 400,
            "title": "Bad Request",
            "detail": f"[Transition cancelled] No verification for user_id={user.id}",
            "message": "Congratulations on your pregnancy! Message your Care Advocate to learn more about Maven’s maternity support.",
        } in res.json["errors"]
        assert track.transitioning_to is None

    @mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    )
    def test_start_transition_with_inactive_verification_with_message(
        self, patch_get_verification_for_user, client, api_helpers, factories
    ):
        user = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.FERTILITY, enabled_tracks=[TrackName.PREGNANCY]
        )
        verification = e9y_factories.VerificationFactory.create(
            user_id=user.id,
            organization_id=user.organization_v2.id,
            eligibility_member_id=1,
            verification_id=2,
        )
        verification.effective_range.upper = (
            datetime.datetime.utcnow().date() - datetime.timedelta(days=365)
        )
        patch_get_verification_for_user.return_value = verification

        track = user.active_tracks[0]
        data = {"destination": TrackName.PREGNANCY}
        res = client.post(
            f"/api/v1/tracks/{track.id}/start-transition",
            headers=api_helpers.json_headers(user),
            data=api_helpers.json_data(data),
        )

        assert {
            "status": 400,
            "title": "Bad Request",
            "detail": f"[Transition cancelled] Verification not active for user_id={user.id}",
            "message": "Congratulations on your pregnancy! Message your Care Advocate to learn more about Maven’s maternity support.",
        } in res.json["errors"]
        assert track.transitioning_to is None

    @mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    )
    def test_start_transition_with_wrong_org_track_with_message(
        self, patch_get_verification_for_user, client, api_helpers, factories
    ):
        user = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.FERTILITY, enabled_tracks=[TrackName.PREGNANCY]
        )
        org = factories.OrganizationFactory.create(
            allowed_tracks=[TrackName.FERTILITY, TrackName.PREGNANCY]
        )
        verification = e9y_factories.VerificationFactory.create(
            user_id=user.id,
            organization_id=org.id,
            eligibility_member_id=1,
            verification_id=2,
        )
        verification.effective_range.upper = (
            datetime.datetime.utcnow().date() + datetime.timedelta(days=365)
        )
        patch_get_verification_for_user.return_value = verification

        track = user.active_tracks[0]
        data = {"destination": TrackName.PREGNANCY}
        res = client.post(
            f"/api/v1/tracks/{track.id}/start-transition",
            headers=api_helpers.json_headers(user),
            data=api_helpers.json_data(data),
        )

        assert {
            "status": 400,
            "title": "Bad Request",
            "detail": f"[Transition cancelled] Verification for user_id={user.id} expected org {user.organization_v2.id} got {org.id}",
            "message": "Congratulations on your pregnancy! Message your Care Advocate to learn more about Maven’s maternity support.",
        } in res.json["errors"]
        assert track.transitioning_to is None

    def test_start_transition_with_non_eligible_track_without_message(
        self, client, api_helpers, mock_fertility_track_eligible_user
    ):
        user = mock_fertility_track_eligible_user
        track = user.active_tracks[0]
        data = {"destination": TrackName.PREGNANCYLOSS}
        res = client.post(
            f"/api/v1/tracks/{track.id}/start-transition",
            headers=api_helpers.json_headers(user),
            data=api_helpers.json_data(data),
        )

        assert {
            "status": 400,
            "title": "Bad Request",
            "detail": f"Organization {user.organization_v2.id} is not configured for Track '{TrackName.PREGNANCYLOSS}'.",
            "message": "",
        } in res.json["errors"]
        assert track.transitioning_to is None


class TestFinishTransition:
    def test_finish_transition(self, client, api_helpers, factories, db):
        user = factories.EnterpriseUserFactory(
            tracks__name=TrackName.PREGNANCY,
            enabled_tracks=[TrackName.PREGNANCY, TrackName.POSTPARTUM],
            health_profile__last_child_birthday=datetime.date.today(),
        )
        track = user.active_tracks[0]
        initiate_transition(track, TrackName.POSTPARTUM)
        assert len(user.member_tracks) == 1
        res = client.post(
            f"/api/v1/tracks/{track.id}/finish-transition",
            headers=api_helpers.json_headers(user),
        )
        assert res.status_code == 200
        db.session.refresh(user)
        assert len(user.member_tracks) == 2


class TestCancelTransition:
    def test_cancel_transition(self, client, api_helpers, factories, db):
        user = factories.EnterpriseUserFactory(
            tracks__name=TrackName.PREGNANCY,
            enabled_tracks=[TrackName.PREGNANCY, TrackName.POSTPARTUM],
            health_profile__last_child_birthday=datetime.date.today(),
        )
        track = user.active_tracks[0]
        initiate_transition(track, TrackName.POSTPARTUM)
        assert user.active_tracks[0].transitioning_to is not None
        res = client.post(
            f"/api/v1/tracks/{track.id}/cancel-transition",
            headers=api_helpers.json_headers(user),
        )
        assert res.status_code == 200
        db.session.refresh(user)
        assert user.active_tracks[0].transitioning_to is None


@pytest.fixture(autouse=True)
def mock_is_user_known_to_be_eligible_for_org():
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.is_user_known_to_be_eligible_for_org",
        autospec=True,
    ) as m:
        m.return_value = True
        yield m


class TestGetTracks:
    def test_get_tracks_response_uses_display_end_date(
        self, client, api_helpers, factories
    ):
        user = factories.EnterpriseUserFactory(tracks__name=TrackName.PREGNANCY)
        track = user.active_tracks[0]
        res = client.get("/api/v1/tracks", headers=api_helpers.json_headers(user))
        returned_track = json.loads(res.data)["active_tracks"][0]
        # Values differ only for pregnancy tracks
        assert (
            returned_track["scheduled_end"]
            != track.get_scheduled_end_date().isoformat()
        )
        assert (
            returned_track["scheduled_end"]
            == track.get_display_scheduled_end_date().isoformat()
        )

    def test_get_tracks_response_contains_track_selection_category(
        self, client, api_helpers, factories, mock_is_user_known_to_be_eligible_for_org
    ):
        org = factories.OrganizationFactory.create()
        pregnancy_client_track = factories.ClientTrackFactory.create(
            organization=org, track=TrackName.PREGNANCY
        )
        factories.ClientTrackFactory.create(
            organization=org, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        user = factories.DefaultUserFactory.create()
        factories.MemberTrackFactory.create(
            user=user, client_track=pregnancy_client_track, name=TrackName.PREGNANCY
        )
        verification = e9y_factories.VerificationFactory.create(
            user_id=user.id,
            organization_id=org.id,
            active_effective_range=True,
        )
        mock_is_user_known_to_be_eligible_for_org.return_value = True
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
            return_value=verification,
        ):
            res = client.get("/api/v1/tracks", headers=api_helpers.json_headers(user))
            data = json.loads(res.data)
            returned_active_track = data["active_tracks"][0]
            assert (
                returned_active_track["track_selection_category"]
                == user.active_tracks[0].track_selection_category
            )
            assert "track_selection_category" in data["available_tracks"][0]

    def test_get_tracks_response_contains_display_length(
        self, client, api_helpers, factories, mock_is_user_known_to_be_eligible_for_org
    ):
        org = factories.OrganizationFactory.create()
        pregnancy_client_track = factories.ClientTrackFactory.create(
            organization=org, track=TrackName.PREGNANCY
        )
        factories.ClientTrackFactory.create(
            organization=org, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        user = factories.DefaultUserFactory.create()
        factories.MemberTrackFactory.create(
            user=user, client_track=pregnancy_client_track, name=TrackName.PREGNANCY
        )
        verification = e9y_factories.VerificationFactory.create(
            user_id=user.id,
            organization_id=org.id,
            active_effective_range=True,
        )
        mock_is_user_known_to_be_eligible_for_org.return_value = True
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
            return_value=verification,
        ):
            res = client.get("/api/v1/tracks", headers=api_helpers.json_headers(user))
            data = json.loads(res.data)
            returned_active_track = data["active_tracks"][0]
            returned_available_track = data["available_tracks"][0]
            returned_transitions = data["active_tracks"][0]["transitions"]
            assert returned_transitions == []
            assert (
                returned_active_track["display_length"]
                == user.active_tracks[0].display_length
                == "Up to 9 months"
            )
            assert (
                returned_active_track["length"]
                == user.active_tracks[0].length().days
                == 294
            )
            assert (
                returned_available_track["display_length"]
                == "Annual renewal up to age 10"
            )
            assert returned_available_track["length_in_days"] is None

    def test_get_tracks_response_contains_transition_list(
        self, client, api_helpers, factories, mock_is_user_known_to_be_eligible_for_org
    ):
        mock_is_user_known_to_be_eligible_for_org.return_value = True
        # postpartum track follows the pregnancy track
        user = factories.EnterpriseUserFactory(
            tracks__name=TrackName.PREGNANCY,
            enabled_tracks=[TrackName.POSTPARTUM],
        )
        res = client.get("/api/v1/tracks", headers=api_helpers.json_headers(user))
        data = json.loads(res.data)
        returned_transitions = data["active_tracks"][0]["transitions"]
        assert returned_transitions[0]["track_length"] == 777

    def test_get_tracks_response_contains_display_length_for_adoption(
        self, client, api_helpers, factories
    ):
        user = factories.EnterpriseUserFactory(tracks__name=TrackName.ADOPTION)
        res = client.get("/api/v1/tracks", headers=api_helpers.json_headers(user))
        data = json.loads(res.data)
        returned_available_track = data["available_tracks"]
        assert returned_available_track == []
        returned_active_track = data["active_tracks"][0]
        assert returned_active_track["name"] == "adoption"
        assert returned_active_track["display_length"] == "12 months"
        assert returned_active_track["length"] == 365
        assert returned_active_track["transitions"] == []

    def test_get_tracks_response_contains_life_stage(
        self, client, api_helpers, factories, mock_is_user_known_to_be_eligible_for_org
    ):
        org = factories.OrganizationFactory.create()
        pregnancy_client_track = factories.ClientTrackFactory.create(
            organization=org, track=TrackName.PREGNANCY
        )
        factories.ClientTrackFactory.create(
            organization=org, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        user = factories.DefaultUserFactory.create()
        factories.MemberTrackFactory.create(
            user=user, client_track=pregnancy_client_track, name=TrackName.PREGNANCY
        )
        verification = e9y_factories.VerificationFactory.create(
            user_id=user.id,
            organization_id=org.id,
            active_effective_range=True,
        )
        mock_is_user_known_to_be_eligible_for_org.return_value = True
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
            return_value=verification,
        ):
            res = client.get("/api/v1/tracks", headers=api_helpers.json_headers(user))
            data = json.loads(res.data)
            returned_active_track = data["active_tracks"][0]
            assert (
                returned_active_track["life_stage"] == user.active_tracks[0].life_stage
            )
            assert "life_stage" in data["available_tracks"][0]

    def test_get_tracks_response_with_no_enabled_track(
        self, client, api_helpers, factories
    ):
        user = factories.EnterpriseUserFactory(tracks__name=TrackName.FERTILITY)
        res = client.get("/api/v1/tracks", headers=api_helpers.json_headers(user))
        active_tracks = json.loads(res.data)["active_tracks"]
        assert (
            active_tracks[0]["name"] == "fertility"
        ), "Expect the active track for test user to be 'fertility'"
        assert (
            active_tracks[0]["transitions"] == []
        ), "Expect the active track to not have any transitions"

    def test_get_tracks_response_with_same_track_name_and_enabled_track(
        self, client, api_helpers, factories
    ):
        user = factories.EnterpriseUserFactory(
            tracks__name=TrackName.TRYING_TO_CONCEIVE,
            enabled_tracks=[TrackName.TRYING_TO_CONCEIVE],
        )
        res = client.get("/api/v1/tracks", headers=api_helpers.json_headers(user))
        active_tracks = json.loads(res.data)["active_tracks"]
        assert (
            active_tracks[0]["name"] == "trying_to_conceive"
        ), "Expect the active track name to be 'trying_to_conceive'"
        assert (
            active_tracks[0]["transitions"] == []
        ), "Expect the active track to not have any transitions"

    def test_get_tracks_response_with_both_transitions(
        self, client, api_helpers, factories, mock_is_user_known_to_be_eligible_for_org
    ):
        mock_is_user_known_to_be_eligible_for_org.return_value = True
        user = factories.EnterpriseUserFactory(
            tracks__name=TrackName.PREGNANCY,
            enabled_tracks=[
                TrackName.PREGNANCY,
                TrackName.PARTNER_PREGNANT,
                TrackName.POSTPARTUM,
                TrackName.PARTNER_NEWPARENT,
                TrackName.ADOPTION,
                TrackName.BREAST_MILK_SHIPPING,
                TrackName.EGG_FREEZING,
                TrackName.FERTILITY,
                TrackName.GENERAL_WELLNESS,
                TrackName.GENERIC,
                TrackName.PARENTING_AND_PEDIATRICS,
                TrackName.PARTNER_FERTILITY,
                TrackName.PREGNANCYLOSS,
                TrackName.PREGNANCY_OPTIONS,
                TrackName.SPONSORED,
                TrackName.SURROGACY,
                TrackName.TRYING_TO_CONCEIVE,
            ],
        )
        res = client.get("/api/v1/tracks", headers=api_helpers.json_headers(user))
        active_tracks = json.loads(res.data)["active_tracks"][0]
        assert (
            active_tracks["name"] == "pregnancy"
        ), "Expect the active track of the test user to be 'pregnancy'"
        assert (
            len(active_tracks["transitions"]) == 2
        ), "Expect 2 transitions to be available for test user"
        assert (
            active_tracks["transitions"][0]["destination"] == "postpartum"
        ), "Expect one of the transition destinations to be 'postpartum'"
        assert (
            active_tracks["transitions"][1]["destination"] == "pregnancyloss"
        ), "Expect the second transition to be 'pregnancyloss'"

    def test_get_tracks_response_with_same_track_name_and_subset_enabled_tracks(
        self, client, api_helpers, factories, mock_is_user_known_to_be_eligible_for_org
    ):
        mock_is_user_known_to_be_eligible_for_org.return_value = True
        user = factories.EnterpriseUserFactory(
            tracks__name=TrackName.PREGNANCY,
            enabled_tracks=[TrackName.POSTPARTUM, TrackName.GENERAL_WELLNESS],
        )
        res = client.get("/api/v1/tracks", headers=api_helpers.json_headers(user))
        current_track = json.loads(res.data)["active_tracks"][0]
        assert (
            current_track["name"] == "pregnancy"
        ), "Expect the active track of the test user to be 'pregnancy'"
        assert (
            len(current_track["transitions"]) == 1
        ), "Expect the test user to have only 1 transition available"
        assert ("destination", "postpartum") in current_track["transitions"][
            0
        ].items(), "Expect the test user transition destination to be 'postpartum'"

    def test_get_tracks_has_no_available_tracks_when_not_eligible_bypass_e9y(
        self, client, api_helpers, factories, mock_is_user_known_to_be_eligible_for_org
    ):
        mock_is_user_known_to_be_eligible_for_org.return_value = False
        user = factories.EnterpriseUserFactory(
            tracks__name=TrackName.PREGNANCY,
            enabled_tracks=[
                TrackName.PREGNANCY,
                TrackName.POSTPARTUM,
                TrackName.PARENTING_AND_PEDIATRICS,
            ],
        )

        res = client.get("/api/v1/tracks", headers=api_helpers.json_headers(user)).json

        assert len(res["available_tracks"]) == 0
        assert len(res["active_tracks"][0]["transitions"]) == 1

    def test_get_tracks_has_no_available_tracks_when_not_eligible(
        self,
        client,
        api_helpers,
        factories,
        mock_is_user_known_to_be_eligible_for_org,
    ):
        mock_is_user_known_to_be_eligible_for_org.return_value = False
        user = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.PREGNANCY,
            enabled_tracks=[
                TrackName.PREGNANCY,
                TrackName.POSTPARTUM,
                TrackName.PARENTING_AND_PEDIATRICS,
            ],
        )

        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
            return_value=None,
        ):
            res = client.get(
                "/api/v1/tracks", headers=api_helpers.json_headers(user)
            ).json
        assert len(res["available_tracks"]) == 0
        assert len(res["active_tracks"][0]["transitions"]) == 1

    def test_get_tracks_has_no_available_tracks_when_not_eligible_transition_not_allowlisted(
        self,
        client,
        api_helpers,
        factories,
        mock_is_user_known_to_be_eligible_for_org,
    ):
        mock_is_user_known_to_be_eligible_for_org.return_value = False
        user = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.GENERAL_WELLNESS,
            enabled_tracks=[
                TrackName.TRYING_TO_CONCEIVE,
                TrackName.GENERAL_WELLNESS,
                TrackName.PARENTING_AND_PEDIATRICS,
            ],
        )

        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
            return_value=None,
        ):
            res = client.get(
                "/api/v1/tracks", headers=api_helpers.json_headers(user)
            ).json
        assert len(res["available_tracks"]) == 0
        assert len(res["active_tracks"][0]["transitions"]) == 0

    def test_get_tracks_has_available_tracks_when_eligible(
        self,
        client,
        api_helpers,
        factories,
        mock_is_user_known_to_be_eligible_for_org,
    ):
        org = factories.OrganizationFactory.create()
        pregnancy_client_track = factories.ClientTrackFactory.create(
            organization=org, track=TrackName.PREGNANCY
        )
        factories.ClientTrackFactory.create(
            organization=org, track=TrackName.PARENTING_AND_PEDIATRICS
        )
        user = factories.DefaultUserFactory.create()
        factories.MemberTrackFactory.create(
            user=user, client_track=pregnancy_client_track, name=TrackName.PREGNANCY
        )
        verification = e9y_factories.VerificationFactory.create(
            user_id=user.id,
            organization_id=org.id,
            active_effective_range=True,
        )
        mock_is_user_known_to_be_eligible_for_org.return_value = True
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
            return_value=verification,
        ):
            res = client.get(
                "/api/v1/tracks", headers=api_helpers.json_headers(user)
            ).json

            assert len(res["available_tracks"]) == 1

    @mock.patch(
        "eligibility.service.EnterpriseVerificationService.is_verification_active"
    )
    @mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    )
    def test_get_localized_tracks(
        self,
        mock_verification,
        mock_is_verification_active,
        client,
        api_helpers,
        factories,
        mock_is_user_known_to_be_eligible_for_org,
    ):
        user = factories.EnterpriseUserFactory(
            tracks__name=TrackName.PREGNANCY,
            enabled_tracks=[
                TrackName.PREGNANCY,
                TrackName.PARENTING_AND_PEDIATRICS,
                TrackName.POSTPARTUM,
                TrackName.PREGNANCYLOSS,
            ],
        )
        mock_is_verification_active.return_value = True
        mock_verification.return_value = VerificationFactory.create(
            user_id=user.id, organization_id=user.organization_v2.id
        )

        verification = e9y_factories.VerificationFactory.create(
            user_id=user.id,
            organization_id=user.organization_v2.id,
            active_effective_range=True,
        )
        mock_is_user_known_to_be_eligible_for_org.return_value = True
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
            return_value=verification,
        ), test_data() as td:
            td.update(td.flag("release-mono-api-localization").variation_for_all(True))
            td.update(
                td.flag("release-track-json-localization").variation_for_all(True)
            )

            res = client.get(
                "/api/v1/tracks",
                headers=api_helpers.with_locale_header(
                    api_helpers.json_headers(user), locale="es"
                ),
            ).json

        assert len(res["active_tracks"]) == 1
        active_track = res["active_tracks"][0]
        assert active_track["display_name"] != "track_config_display_name_pregnancy"
        assert len(active_track["transitions"]) == 2
        assert (
            active_track["transitions"][0]["description"]
            != "track_config_display_description_i_have_given_birth"
        )

        assert len(res["available_tracks"]) == 1
        assert (
            res["available_tracks"][0]["display_name"]
            != "track_config_display_name_parenting_pediatrics"
        )

    def test_get_tracks_response_with_cancel_renewal_cta(
        self, client, api_helpers, factories
    ):
        user = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.ADOPTION,
            tracks__anchor_date=datetime.date(2021, 1, 1),
        )
        scheduled_track = factories.MemberTrackFactory.create(
            name=TrackName.ADOPTION,
            user=user,
            previous_member_track_id=user.active_tracks[0].id,
        )
        scheduled_track.activated_at = None

        res = client.get("/api/v1/tracks", headers=api_helpers.json_headers(user)).json
        active_track = res["active_tracks"][0]
        cta = active_track["cta"]

        assert (
            active_track["status_description"]
            == "Scheduled to renew on January 15, 2022."
        )
        assert cta is not None
        assert cta["text"] == "Cancel"
        assert cta["action"] == "CANCEL_RENEWAL"

    @freezegun.freeze_time("2022-01-01 12:00:00.0")
    def test_get_tracks_response_with_schedule_renewal_cta(
        self, client, api_helpers, factories
    ):
        user = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.ADOPTION,
            tracks__anchor_date=datetime.date(2021, 1, 1),
        )

        res = client.get("/api/v1/tracks", headers=api_helpers.json_headers(user)).json
        active_track = res["active_tracks"][0]
        cta = active_track["cta"]

        assert (
            active_track["status_description"]
            == "Your access will end on January 15, 2022."
        )
        assert cta is not None
        assert cta["text"] == "Renew program"
        assert cta["action"] == "SCHEDULE_RENEWAL"

    @freezegun.freeze_time("2021-03-01 12:00:00.0")
    def test_get_tracks_response_no_cta_if_track_doesnt_end_soon(
        self, client, api_helpers, factories
    ):
        user = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.ADOPTION,
            tracks__anchor_date=datetime.date(2021, 1, 1),
        )

        res = client.get("/api/v1/tracks", headers=api_helpers.json_headers(user)).json
        active_track = res["active_tracks"][0]

        assert active_track["status_description"] is None
        assert active_track["cta"] is None


class TestRenewTrack:
    def test_renew_track(self, client, api_helpers, factories):
        active_track = factories.MemberTrackFactory.create(
            name=TrackName.SURROGACY,
        )

        user = active_track.user

        assert len(user.active_tracks) == 1
        assert len(user.scheduled_tracks) == 0

        with mock.patch(
            "tracks.repository.MemberTrackRepository.get"
        ) as mock_member_tracks_get:
            mock_member_tracks_get.return_value = active_track
            res = client.post(
                f"/api/v1/tracks/{active_track.id}/renewal",
                headers=api_helpers.json_headers(user),
            )

        data = api_helpers.load_json(res)

        db.session.expire_all()

        assert res.status_code == 201
        assert data["success"] is True

        assert len(user.active_tracks) == 1
        assert len(user.scheduled_tracks) == 1

        renewed_track = user.scheduled_tracks[0]

        assert data["track_id"] == renewed_track.id
        assert (
            data["scheduled_end_date"]
            == renewed_track.get_scheduled_end_date().isoformat()
        )

    def test_renew_track__track_not_associated_with_user(
        self, client, api_helpers, factories
    ):
        active_track = factories.MemberTrackFactory.create(
            name=TrackName.PREGNANCY,
        )

        user = factories.EnterpriseUserFactory.create()

        assert user != active_track.user
        assert len(user.active_tracks) == 1
        assert len(user.inactive_tracks) == 0
        assert len(user.scheduled_tracks) == 0

        res = client.post(
            f"/api/v1/tracks/{active_track.id}/renewal",
            headers=api_helpers.json_headers(user),
        )

        assert res.status_code == 404

        assert len(user.active_tracks) == 1
        assert len(user.inactive_tracks) == 0
        assert len(user.scheduled_tracks) == 0

    def test_renew_track__track_not_renewable(self, client, api_helpers, factories):
        active_track = factories.MemberTrackFactory.create(
            name=TrackName.PREGNANCY,
        )

        user = active_track.user

        assert len(user.active_tracks) == 1
        assert len(user.inactive_tracks) == 0
        assert len(user.scheduled_tracks) == 0

        res = client.post(
            f"/api/v1/tracks/{active_track.id}/renewal",
            headers=api_helpers.json_headers(user),
        )

        assert res.status_code == 400

        assert len(user.active_tracks) == 1
        assert len(user.inactive_tracks) == 0
        assert len(user.scheduled_tracks) == 0

    def test_renew_track__track_is_inactive(self, client, api_helpers, factories):
        inactive_track = factories.MemberTrackFactory.create(
            name=TrackName.SURROGACY,
            start_date=datetime.datetime.now().date() + datetime.timedelta(weeks=3),
            ended_at=datetime.datetime.utcnow() - datetime.timedelta(weeks=2),
        )

        user = inactive_track.user

        assert len(user.active_tracks) == 0
        assert len(user.inactive_tracks) == 1
        assert len(user.scheduled_tracks) == 0

        res = client.post(
            f"/api/v1/tracks/{inactive_track.id}/renewal",
            headers=api_helpers.json_headers(user),
        )

        assert res.status_code == 404

        assert len(user.active_tracks) == 0
        assert len(user.inactive_tracks) == 1
        assert len(user.scheduled_tracks) == 0

    def test_renew_track__track_already_renewed(self, client, api_helpers, factories):
        active_track = factories.MemberTrackFactory.create(
            name=TrackName.SURROGACY,
        )

        user = active_track.user

        factories.MemberTrackFactory.create(
            user=user,
            name=active_track.name,
            start_date=datetime.datetime.now().date() + datetime.timedelta(weeks=2),
        ).activated_at = None

        db.session.refresh(user)

        assert len(user.active_tracks) == 1
        assert len(user.inactive_tracks) == 0
        assert len(user.scheduled_tracks) == 1

        res = client.post(
            f"/api/v1/tracks/{active_track.id}/renewal",
            headers=api_helpers.json_headers(user),
        )

        assert res.status_code == 400

        assert len(user.active_tracks) == 1
        assert len(user.inactive_tracks) == 0
        assert len(user.scheduled_tracks) == 1


class TestScheduledTrackCancellation:
    def test_cancel_scheduled_track(self, client, api_helpers, factories):
        ending_track = factories.MemberTrackFactory.create(
            name=TrackName.SURROGACY,
            anchor_date=datetime.datetime.utcnow().date()
            - datetime.timedelta(days=360),
        )
        user = ending_track.user

        scheduled_track = factories.MemberTrackFactory.create(
            user=user,
            name=TrackName.SURROGACY,
            start_date=ending_track.get_scheduled_end_date(),
            previous_member_track_id=ending_track.id,
        )
        scheduled_track.activated_at = None
        db.session.refresh(user)

        assert len(user.active_tracks) == 1
        assert len(user.scheduled_tracks) == 1

        res = client.delete(
            f"/api/v1/tracks/{ending_track.id}/scheduled",
            headers=api_helpers.json_headers(user),
        )

        db.session.expire_all()

        assert res.status_code == 204

        assert len(user.active_tracks) == 1
        assert len(user.scheduled_tracks) == 0

    def test_cancel_scheduled_track__no_scheduled_track(
        self, client, api_helpers, factories
    ):
        ending_track = factories.MemberTrackFactory.create(
            name=TrackName.SURROGACY,
            anchor_date=datetime.datetime.utcnow().date()
            - datetime.timedelta(days=360),
        )
        user = ending_track.user

        assert len(user.active_tracks) == 1
        assert len(user.scheduled_tracks) == 0

        res = client.delete(
            f"/api/v1/tracks/{ending_track.id}/scheduled",
            headers=api_helpers.json_headers(user),
        )

        db.session.expire_all()

        assert res.status_code == 404

        assert len(user.active_tracks) == 1
        assert len(user.scheduled_tracks) == 0

    def test_cancel_scheduled_track__different_scheduled_track(
        self, client, api_helpers, factories
    ):
        ending_track = factories.MemberTrackFactory.create(
            name=TrackName.SURROGACY,
            anchor_date=datetime.datetime.utcnow().date()
            - datetime.timedelta(days=360),
        )
        user = ending_track.user

        scheduled_track = factories.MemberTrackFactory.create(
            user=user,
            name=TrackName.ADOPTION,
            start_date=ending_track.get_scheduled_end_date(),
            previous_member_track_id=ending_track.id,
        )
        scheduled_track.activated_at = None
        db.session.refresh(user)

        assert len(user.active_tracks) == 1
        assert len(user.scheduled_tracks) == 1

        res = client.delete(
            f"/api/v1/tracks/{ending_track.id}/scheduled",
            headers=api_helpers.json_headers(user),
        )

        db.session.expire_all()

        assert res.status_code == 204

        assert len(user.active_tracks) == 1
        assert len(user.scheduled_tracks) == 0

    def test_cancel_scheduled_track__previous_renewal(
        self, client, api_helpers, factories
    ):
        old_track = factories.MemberTrackFactory.create(
            ended_at=datetime.datetime.utcnow() - datetime.timedelta(days=7)
        )
        user = old_track.user
        ending_track = factories.MemberTrackFactory.create(
            user=user,
            name=TrackName.SURROGACY,
            anchor_date=datetime.datetime.utcnow().date()
            - datetime.timedelta(days=360),
            previous_member_track_id=old_track.id,
        )

        scheduled_track = factories.MemberTrackFactory.create(
            user=user,
            name=TrackName.ADOPTION,
            start_date=ending_track.get_scheduled_end_date(),
            previous_member_track_id=ending_track.id,
        )
        scheduled_track.activated_at = None
        db.session.refresh(user)

        assert len(user.inactive_tracks) == 1
        assert len(user.active_tracks) == 1
        assert len(user.scheduled_tracks) == 1

        res = client.delete(
            f"/api/v1/tracks/{ending_track.id}/scheduled",
            headers=api_helpers.json_headers(user),
        )

        db.session.expire_all()

        assert res.status_code == 204

        assert len(user.inactive_tracks) == 1
        assert len(user.active_tracks) == 1
        assert len(user.scheduled_tracks) == 0

    def test_cancel_scheduled_track__exception(self, client, api_helpers, factories):
        ending_track = factories.MemberTrackFactory.create(
            name=TrackName.SURROGACY,
            anchor_date=datetime.datetime.utcnow().date()
            - datetime.timedelta(days=360),
        )
        user = ending_track.user

        scheduled_track = factories.MemberTrackFactory.create(
            user=user,
            name=TrackName.SURROGACY,
            start_date=ending_track.get_scheduled_end_date(),
            previous_member_track_id=ending_track.id,
        )
        scheduled_track.activated_at = None
        db.session.refresh(user)

        assert len(user.active_tracks) == 1
        assert len(user.scheduled_tracks) == 1

        with mock.patch("views.tracks.terminate") as mock_terminate:
            mock_terminate.side_effect = TrackLifecycleError()
            res = client.delete(
                f"/api/v1/tracks/{ending_track.id}/scheduled",
                headers=api_helpers.json_headers(user),
            )

            db.session.expire_all()

            assert res.status_code == 400

            assert len(user.active_tracks) == 1
            assert len(user.scheduled_tracks) == 1


class TestIntroAppointmentEligibility:
    url_prefix = "/api/v1/tracks/intro_appointment_eligibility"

    def test_intro_appointment_eligibility__unauthenticated_user(
        self, client, api_helpers
    ):
        res = client.get(
            self.url_prefix,
            headers=api_helpers.json_headers(),
        )
        assert res.status_code == 401

    def test_intro_appointment_eligibility__mising_track_names(
        self, client, api_helpers, default_user
    ):
        res = client.get(
            self.url_prefix,
            headers=api_helpers.json_headers(default_user),
        )
        assert res.status_code == 400
        assert (
            api_helpers.load_json(res)["errors"][0]["detail"]
            == "Missing data for required field."
        )

    @pytest.mark.parametrize(
        argnames="track_names, invalid_track_name",
        argvalues=[
            (["something_invalid", "something_invalid"]),
            (["pregnancy,something_invalid", "something_invalid"]),
        ],
    )
    def test_intro_appointment_eligibility__invalid_track_names(
        self,
        track_names,
        invalid_track_name,
        client,
        api_helpers,
        default_user,
    ):

        res = client.get(
            f"{self.url_prefix}?tracks={track_names}",
            headers=api_helpers.json_headers(default_user),
        )
        assert res.status_code == 400

        expected_error_msg = f"{invalid_track_name} is not a configured Track in {str(TRACK_CONFIG_L10N)!r}."
        assert api_helpers.load_json(res)["errors"][0]["detail"] == expected_error_msg

    @pytest.mark.parametrize(
        argnames="track_name,track_eligible",
        argvalues=[
            ("pregnancy", True),
            ("menopause", True),
            ("postpartum", True),
            ("adoption", True),
            ("egg_freezing", True),
            ("fertility", True),
            ("surrogacy", True),
            ("trying_to_conceive", True),
            ("pregnancyloss", True),
            ("general_wellness", False),
            ("generic", False),
            ("parenting_and_pediatrics", False),
            ("pregnancy_options", False),
            ("sponsored", False),
            ("breast_milk_shipping", False),
            ("partner_fertility", False),
            ("partner_newparent", False),
            ("partner_pregnant", False),
        ],
    )
    def test_intro_appointment_eligibility__query_one_track(
        self,
        track_name,
        track_eligible,
        client,
        api_helpers,
        default_user,
        mock_intro_appointment_flag,
    ):
        mock_intro_appointment_flag(
            "pregnancy, menopause, postpartum, fertility, pregnancyloss, trying_to_conceive, egg_freezing, adoption, surrogacy"
        )
        res = client.get(
            f"{self.url_prefix}?tracks={track_name}",
            headers=api_helpers.json_headers(default_user),
        )
        assert res.status_code == 200
        assert (
            api_helpers.load_json(res)["eligible_for_intro_appointment"]
            == track_eligible
        )

    @pytest.mark.parametrize(
        argnames="track_name,track_eligible",
        argvalues=[
            ("pregnancy,menopause", True),
            ("pregnancy,general_wellness", True),
            ("general_wellness,generic", False),
        ],
    )
    def test_intro_appointment_eligibility__query_set_of_tracks(
        self,
        track_name,
        track_eligible,
        client,
        api_helpers,
        default_user,
        mock_intro_appointment_flag,
    ):
        mock_intro_appointment_flag(
            "pregnancy, menopause, postpartum, fertility, pregnancyloss, trying_to_conceive, egg_freezing, adoption, surrogacy"
        )
        res = client.get(
            f"{self.url_prefix}?tracks={track_name}",
            headers=api_helpers.json_headers(default_user),
        )
        assert res.status_code == 200
        assert (
            api_helpers.load_json(res)["eligible_for_intro_appointment"]
            == track_eligible
        )
