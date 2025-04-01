from models.enterprise import OnboardingState
from pytests import factories


def test_update_onboarding_state_enterprise_user(client, api_helpers):
    # Given
    user = factories.EnterpriseUserFactory.create()
    url = f"/api/v1/users/{user.id}/onboarding_state"
    # When
    res = client.post(url, headers=api_helpers.json_headers(user))
    # Enterprise users should not be able to update onboarding state with this endpoint
    assert res.status_code == 201
    assert user.onboarding_state.state == OnboardingState.USER_CREATED


def test_update_onboarding_state_marketplace_user(client, api_helpers):
    # Given
    user = factories.DefaultUserFactory.create()
    url = f"/api/v1/users/{user.id}/onboarding_state"
    # When
    res = client.post(
        url,
        data="[]",
        headers=api_helpers.json_headers(user),
    )
    # Then
    # Marketplace users should be able to update onboarding state with this endpoint
    assert res.status_code == 201
    assert user.onboarding_state.state == OnboardingState.USER_CREATED
