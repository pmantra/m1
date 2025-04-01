from unittest import mock

import pytest

from eligibility.pytests import factories as e9y_factories
from eligibility.pytests.factories import EligibilityMemberFactory
from eligibility.utils.feature_flags import OVER_ELIGIBILITY
from models.enterprise import OnboardingState
from models.tracks import TrackName
from storage.connection import db
from utils.onboarding_state import update_onboarding_state


@pytest.fixture
def patch_send_onboarding_state():
    with mock.patch(
        "braze.attributes.send_onboarding_state_to_braze"
    ) as send_onboarding_state:
        yield send_onboarding_state.delay


@pytest.fixture
def patch_tracks_initiate(factories):
    with mock.patch("models.tracks.initiate") as initiate:
        initiate.return_value = factories.MemberTrackFactory.create(name="pregnancy")
        yield initiate


@pytest.fixture
def mock_overeligibility_enabled(ff_test_data):
    def _mock(is_on: bool = False):
        ff_test_data.update(
            ff_test_data.flag(OVER_ELIGIBILITY).variation_for_all(is_on)
        )

    return _mock


@pytest.fixture(autouse=True)
def mock_braze_enabled(ff_test_data):
    ff_test_data.update(
        ff_test_data.flag("kill-switch-braze-api-requests").variation_for_all(True)
    )


class TestOnboardingState:
    def test_onboarding_state_transitions(
        self,
        default_user,
        factories,
        client,
        api_helpers,
        mock_e9y_service,
        patch_send_onboarding_state,
        patch_tracks_initiate,
    ):
        """
        Start from UserCreated onboarding state, hit endpoints that change onboarding states and validate that changes occur
        """
        allowed_tracks = {TrackName.ADOPTION, TrackName.BREAST_MILK_SHIPPING}
        org = factories.OrganizationFactory.create(allowed_tracks=allowed_tracks)
        employee = factories.OrganizationEmployeeFactory.create(
            organization=org, unique_corp_id=None
        )
        factories.UserOrganizationEmployeeFactory.create(
            user=default_user,
            organization_employee=employee,
        )
        verification = e9y_factories.VerificationFactory.create(
            user_id=default_user.id, organization_id=org.id
        )
        update_onboarding_state(default_user, OnboardingState.USER_CREATED)
        patch_send_onboarding_state.assert_called_once_with(
            default_user.esp_id, OnboardingState.USER_CREATED
        )
        patch_send_onboarding_state.reset_mock()

        eligibility_member = EligibilityMemberFactory.create(
            organization_id=org.id,
            first_name=employee.first_name,
            last_name=employee.last_name,
            date_of_birth=employee.date_of_birth,
        )

        mock_e9y_service.standard.return_value = eligibility_member

        # Hit GET /features and validate onboarding_state doesn't change or call Braze (in the future it should change to TRACK_SELECTION)
        with mock.patch("eligibility.web.verify_member") as mock_verify_members:
            mock_verify_members.return_value = verification
            res = client.get(
                "/api/v1/features",
                headers=api_helpers.standard_headers(default_user),
                query_string={
                    "date_of_birth": employee.date_of_birth.isoformat(),
                    "company_email": employee.email,
                },
            )
        assert res.status_code == 200
        assert default_user.onboarding_state.state == OnboardingState.USER_CREATED
        patch_send_onboarding_state.assert_not_called()

        # Hit POST /organizations and validate onboarding_state changes to ASSESSMENTS
        with mock.patch("eligibility.verify_members") as mock_verify_members:
            mock_verify_members.return_value = [verification]
            res = client.post(
                f"/api/v1/users/{default_user.id}/organizations",
                headers=api_helpers.json_headers(default_user),
                data=api_helpers.json_data({}),
            )
        assert res.status_code == 201
        assert default_user.onboarding_state.state == OnboardingState.ASSESSMENTS
        patch_send_onboarding_state.assert_called_once_with(
            default_user.esp_id, OnboardingState.ASSESSMENTS
        )
        patch_send_onboarding_state.reset_mock()

    def test_update_onboarding_state_no_user_onboarding_state(
        self, default_user, patch_send_onboarding_state
    ):
        # Given
        assert default_user.onboarding_state is None
        # When
        update_onboarding_state(default_user, OnboardingState.TRACK_SELECTION)
        db.session.commit()
        # Then
        assert default_user.onboarding_state.state == OnboardingState.TRACK_SELECTION
        patch_send_onboarding_state.assert_called_with(
            default_user.esp_id, OnboardingState.TRACK_SELECTION
        )

    def test_update_onboarding_state_existing_user_onboarding_state(
        self, default_user, factories, patch_send_onboarding_state
    ):
        # Given
        factories.UserOnboardingStateFactory.create(
            user=default_user, state=OnboardingState.USER_CREATED
        )
        # When
        update_onboarding_state(default_user, OnboardingState.TRACK_SELECTION)
        db.session.commit()
        # Then
        assert default_user.onboarding_state.state == OnboardingState.TRACK_SELECTION
        patch_send_onboarding_state.assert_called_with(
            default_user.esp_id, OnboardingState.TRACK_SELECTION
        )

    def test_update_onboarding_state_api(
        self, default_user, factories, client, api_helpers, patch_send_onboarding_state
    ):
        # Given
        factories.UserOnboardingStateFactory.create(
            user=default_user, state=OnboardingState.USER_CREATED
        )
        # When
        res = client.put(
            f"/api/v1/users/{default_user.id}/onboarding_state",
            json={"onboarding_state": OnboardingState.TRACK_SELECTION.value},
            headers=api_helpers.standard_headers(default_user),
        )
        assert (
            api_helpers.load_json(res)["onboarding_state"]
            == OnboardingState.TRACK_SELECTION.value
        )
        assert res.status_code == 200
        patch_send_onboarding_state.assert_called_with(
            default_user.esp_id, OnboardingState.TRACK_SELECTION
        )

    def test_API_update_onboarding_state_no_user_onboarding_state(
        self, default_user, client, api_helpers, patch_send_onboarding_state
    ):
        # Given
        assert default_user.onboarding_state is None
        # When
        res = client.put(
            f"/api/v1/users/{default_user.id}/onboarding_state",
            json={"onboarding_state": OnboardingState.TRACK_SELECTION.value},
            headers=api_helpers.standard_headers(default_user),
        )
        assert (
            api_helpers.load_json(res)["onboarding_state"]
            == OnboardingState.TRACK_SELECTION.value
        )
        assert res.status_code == 200
        patch_send_onboarding_state.assert_called_with(
            default_user.esp_id, OnboardingState.TRACK_SELECTION
        )

    def test_update_onboarding_state_api_bad_state(
        self, default_user, factories, client, api_helpers, patch_send_onboarding_state
    ):
        # Given
        factories.UserOnboardingStateFactory.create(
            user=default_user, state=OnboardingState.USER_CREATED
        )
        # When
        res = client.put(
            f"/api/v1/users/{default_user.id}/onboarding_state",
            json={"onboarding_state": "foobar!"},
            headers=api_helpers.standard_headers(default_user),
        )
        assert api_helpers.load_json(res)["message"] == "foobar! does not exist"
        assert res.status_code == 400
        patch_send_onboarding_state.assert_not_called()

    def test_get_onboarding_state(self, default_user, factories, client, api_helpers):
        # Given -  starting with no state
        assert default_user.onboarding_state is None

        res = client.get(
            f"/api/v1/users/{default_user.id}/onboarding_state",
            headers=api_helpers.standard_headers(default_user),
        )
        # Then
        assert res.status_code == 200
        assert api_helpers.load_json(res)["onboarding_state"] is None

        # Given
        factories.UserOnboardingStateFactory.create(
            user=default_user, state=OnboardingState.USER_CREATED
        )
        assert default_user.onboarding_state.state == OnboardingState.USER_CREATED

        # Then
        # Hit GET /users/{id}/onboarding_state and validate onboarding_state is the same
        res = client.get(
            f"/api/v1/users/{default_user.id}/onboarding_state",
            headers=api_helpers.standard_headers(default_user),
        )
        assert res.status_code == 200
        assert (
            api_helpers.load_json(res)["onboarding_state"]
            == default_user.onboarding_state.state
        )
