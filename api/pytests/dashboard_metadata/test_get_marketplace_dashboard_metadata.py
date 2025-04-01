import pytest

from models.enterprise import OnboardingState, UserOnboardingState
from preferences.resources.member_communications import (
    set_member_communications_preference,
)


@pytest.mark.parametrize(
    argnames="onboarding_state, onboarding_state_value",
    argvalues=[
        (OnboardingState.USER_CREATED, "user_created"),
        (OnboardingState.TRACK_SELECTION, "track_selection"),
        (OnboardingState.FAILED_TRACK_SELECTION, "failed_track_selection"),
        (OnboardingState.FAILED_ELIGIBILITY, "failed_eligibility"),
    ],
)
def test_get_marketplace_dashboard_metadata(
    default_user, client, api_helpers, onboarding_state, onboarding_state_value
):
    # testing for these responses as they are configured with these strings for personalization in contentful
    default_user.onboarding_state = UserOnboardingState(state=onboarding_state)
    res = client.get(
        "api/v1/dashboard-metadata/marketplace",
        headers=api_helpers.json_headers(user=default_user),
    ).json

    assert res["first_name"] == default_user.first_name
    assert res["onboarding_state"] == onboarding_state_value
    assert res["has_recently_ended_track"] is False


def test_get_marketplace_dashboard_metadata__practitioner(
    client, api_helpers, factories
):
    practitioner = factories.PractitionerUserFactory.create()
    res = client.get(
        "api/v1/dashboard-metadata/marketplace",
        headers=api_helpers.json_headers(user=practitioner),
    ).json

    assert practitioner.member_profile is None
    assert res["first_name"] == practitioner.first_name
    assert res["onboarding_state"] is None
    assert res["has_recently_ended_track"] is False


def test_get_marketplace_dashboard_metadata_onboarding_state_none(
    default_user, client, api_helpers
):
    res = client.get(
        "api/v1/dashboard-metadata/marketplace",
        headers=api_helpers.json_headers(user=default_user),
    ).json

    assert res["first_name"] == default_user.first_name
    assert res["onboarding_state"] is None
    assert res["has_recently_ended_track"] is False


@pytest.mark.parametrize("preference_value", [True, False])
def test_get_dashboard_metadata_marketplace_has_email_preference(
    default_user, client, api_helpers, factories, preference_value
):
    factories.MemberProfileFactory.create(
        user_id=default_user.id,
    )
    set_member_communications_preference(default_user.id, preference_value)
    res = client.get(
        "api/v1/dashboard-metadata/marketplace",
        headers=api_helpers.standard_headers(user=default_user),
    )

    assert res.status_code == 200
    assert res.json["subscribed_to_promotional_email"] is preference_value
