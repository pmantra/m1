import datetime
import json
from unittest import mock

from maven.feature_flags import TestData, test_data

from eligibility.pytests import factories as e9y_factories
from models import enterprise, tracks
from models.tracks import TrackName
from pytests import factories


def test_enroll_user_happy_path(
    client, api_helpers, verification, mock_overeligibility_enabled
):
    # Given
    given_due_date = datetime.datetime.utcnow() + datetime.timedelta(days=180)
    given_user = factories.MemberFactory.create(health_profile__due_date=given_due_date)
    given_url = f"/api/v1/users/{given_user.id}/organizations"
    given_data = {"verification_reason": tracks.TrackName.PREGNANCY.value}
    expected_status_code = 201
    expected_onboarding_state = enterprise.OnboardingState.ASSESSMENTS

    org = factories.OrganizationFactory.create(allowed_tracks=[*TrackName])
    verification = e9y_factories.VerificationFactory.create(
        user_id=given_user.id,
        organization_id=org.id,
        active_effective_range=True,
    )
    mock_overeligibility_enabled(False)
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), mock.patch(
        "eligibility.repository.OrganizationRepository.get_enablement"
    ), mock.patch(
        "eligibility.verify_member"
    ) as mock_verify_member:
        # When
        mock_verify_member.return_value = verification
        res = client.post(
            given_url,
            headers=api_helpers.json_headers(given_user),
            data=api_helpers.json_data(given_data),
        )
    # Then
    assert res.status_code == expected_status_code
    assert given_user.onboarding_state.state == expected_onboarding_state
    json_data = json.loads(res.data)
    assert json_data["can_invite_partner"] == True
    assert len(json_data["eligible_features"]) > 0


def test_enroll_user_specific_org(
    client,
    api_helpers,
    verification,
    ff_test_data: TestData,
    mock_overeligibility_enabled,
):
    # Given
    ff_test_data.update(
        ff_test_data.flag(
            "overeligibility-create-tracks",
        ).value_for_all(True),
    )
    mock_overeligibility_enabled(False)
    given_due_date = datetime.datetime.utcnow() + datetime.timedelta(days=180)
    given_user = factories.MemberFactory.create(health_profile__due_date=given_due_date)
    org = factories.OrganizationFactory.create(allowed_tracks=[*TrackName])
    verification = e9y_factories.VerificationFactory.create(
        user_id=given_user.id,
        organization_id=org.id,
        active_effective_range=True,
    )
    given_url = f"/api/v1/users/{given_user.id}/organizations"
    given_data = {
        "verification_reason": tracks.TrackName.PREGNANCY.value,
        "organization_id": "1000",
    }
    expected_status_code = 201
    expected_onboarding_state = enterprise.OnboardingState.ASSESSMENTS

    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), mock.patch(
        "eligibility.repository.OrganizationRepository.get_enablement"
    ), mock.patch(
        "eligibility.verify_member"
    ) as mock_verify_member, test_data():
        mock_verify_member.return_value = verification
        res = client.post(
            given_url,
            headers=api_helpers.json_headers(given_user),
            data=api_helpers.json_data(given_data),
        )
        expected_args = {
            "user_id": given_user.id,
            "client_params": {"verification_type": "lookup"},
        }
        # Then
        mock_verify_member.assert_called_with(**expected_args)
    assert res.status_code == expected_status_code
    assert given_user.onboarding_state.state == expected_onboarding_state


def test_enroll_user_invalid_track(
    client, api_helpers, verification, mock_overeligibility_enabled
):
    # Given
    mock_overeligibility_enabled(False)
    given_due_date = datetime.datetime.utcnow() + datetime.timedelta(days=180)
    given_user = factories.MemberFactory.create(health_profile__due_date=given_due_date)
    given_url = f"/api/v1/users/{given_user.id}/organizations"
    given_data = {"verification_reason": "super_pregnant"}
    expected_status_code = 201
    expected_onboarding_state = enterprise.OnboardingState.FAILED_TRACK_SELECTION
    # When
    with mock.patch(
        "eligibility.repository.OrganizationRepository.get_enablement"
    ), mock.patch("eligibility.verify_member") as mock_verify_member:
        mock_verify_member.return_value = verification
        res = client.post(
            given_url,
            headers=api_helpers.json_headers(given_user),
            data=api_helpers.json_data(given_data),
        )
    # Then
    assert res.status_code == expected_status_code
    assert given_user.onboarding_state.state == expected_onboarding_state


def test_enroll_user_missing_information(
    client, api_helpers, verification, mock_overeligibility_enabled
):
    # Given
    given_user = factories.MemberFactory.create(health_profile__due_date=None)
    mock_overeligibility_enabled(False)
    given_url = f"/api/v1/users/{given_user.id}/organizations"
    given_data = {"verification_reason": tracks.TrackName.PREGNANCY.value}
    expected_status_code = 422
    expected_onboarding_state = enterprise.OnboardingState.FAILED_TRACK_SELECTION
    # When
    with mock.patch(
        "eligibility.repository.OrganizationRepository.get_enablement"
    ), mock.patch("eligibility.verify_member") as mock_verify_member:
        mock_verify_member.return_value = verification
        res = client.post(
            given_url,
            headers=api_helpers.json_headers(given_user),
            data=api_helpers.json_data(given_data),
        )
    # Then
    assert res.status_code == expected_status_code
    assert given_user.onboarding_state.state == expected_onboarding_state


def test_enroll_user_invalid_user_information(
    client, api_helpers, verification, mock_overeligibility_enabled
):
    # Given
    given_due_date = datetime.datetime.utcnow() - datetime.timedelta(days=180)
    given_user = factories.MemberFactory.create(health_profile__due_date=given_due_date)
    mock_overeligibility_enabled(False)
    given_url = f"/api/v1/users/{given_user.id}/organizations"
    given_data = {"verification_reason": tracks.TrackName.PREGNANCY.value}
    expected_status_code = 422
    expected_onboarding_state = enterprise.OnboardingState.FAILED_TRACK_SELECTION
    # When
    with mock.patch(
        "eligibility.repository.OrganizationRepository.get_enablement"
    ), mock.patch("eligibility.verify_member") as mock_verify_member:
        mock_verify_member.return_value = verification
        res = client.post(
            given_url,
            headers=api_helpers.json_headers(given_user),
            data=api_helpers.json_data(given_data),
        )
    # Then
    assert res.status_code == expected_status_code
    assert given_user.onboarding_state.state == expected_onboarding_state


def expect_scheduled_end_date(
    client,
    api_helpers,
    flag_enabled,
    scheduled_end_date_request,
):
    user = factories.MemberFactory.create()
    org = factories.OrganizationFactory.create(allowed_tracks=[*TrackName])
    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id,
        organization_id=org.id,
        active_effective_range=True,
    )

    request_data = {
        "verification_reason": tracks.TrackName.PARENTING_AND_PEDIATRICS.value,
        "scheduled_end_date": scheduled_end_date_request.isoformat(),
    }

    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), mock.patch(
        "eligibility.repository.OrganizationRepository.get_enablement"
    ), mock.patch(
        "eligibility.verify_member"
    ) as mock_verify_member, test_data() as td:
        mock_verify_member.return_value = verification
        td.update(
            td.flag("enable-configure-track-scheduled-end-date").variation_for_all(
                flag_enabled
            )
        )

        res = client.post(
            f"/api/v1/users/{user.id}/organizations",
            headers=api_helpers.json_headers(user),
            data=api_helpers.json_data(request_data),
        )

    assert res.status_code == 201

    return user.active_tracks[0].get_scheduled_end_date()


def test_enroll_user_with_scheduled_end_date_and_flag_disabled(client, api_helpers):
    scheduled_end_date_in_request = datetime.date.today() + datetime.timedelta(days=15)

    scheduled_end_date = expect_scheduled_end_date(
        client, api_helpers, False, scheduled_end_date_in_request
    )

    assert scheduled_end_date != scheduled_end_date_in_request


def test_enroll_user_with_scheduled_end_date_and_flag_enabled(client, api_helpers):
    scheduled_end_date_in_request = datetime.date.today() + datetime.timedelta(days=15)

    scheduled_end_date = expect_scheduled_end_date(
        client, api_helpers, True, scheduled_end_date_in_request
    )

    assert scheduled_end_date == scheduled_end_date_in_request
