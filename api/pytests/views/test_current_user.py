from datetime import datetime

from authn.models.user import MFAState
from models.enterprise import OnboardingState, UserOnboardingState


def test_get_user_when_member(client, api_helpers, factories):
    img = factories.ImageFactory.create()
    user = factories.EnterpriseUserFactory(
        image_id=img.id,
        onboarding_state=UserOnboardingState(state=OnboardingState.TRACK_SELECTION),
        mfa_state=MFAState.ENABLED,
        sms_phone_number="+12015550123",
    )
    factories.HealthProfileFactory.create(
        user=user, birthday=datetime.strptime("2000-01-01", "%Y-%m-%d")
    )

    res = client.get("/api/v1/users/me", headers=api_helpers.standard_headers(user))
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json["id"] == user.id
    assert json["first_name"] == user.first_name
    assert json["middle_name"] == user.middle_name
    assert json["last_name"] == user.last_name
    assert json["email"] == user.email
    assert json["name"] == user.full_name
    assert json["username"] == user.username
    assert json["date_of_birth"] == "2000-01-01"
    assert json["role"] == "member"
    assert json["onboarding_state"] == OnboardingState.TRACK_SELECTION.value
    assert json["esp_id"] == user.esp_id
    assert json["encoded_id"] is not None
    assert json["avatar_url"] == user.avatar_url
    assert json["image_id"] == img.id
    assert json["image_url"] == user.avatar_url
    assert json["mfa_state"] == MFAState.ENABLED.value
    assert json["sms_phone_number"] == "+12015550123"
    assert json["bright_jwt"] is not None


def test_get_user_when_practitioner(client, api_helpers, factories):
    user = factories.PractitionerUserFactory()

    res = client.get("/api/v1/users/me", headers=api_helpers.standard_headers(user))
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json["id"] == user.id
    assert json["role"] == "practitioner"


def test_get_user_when_unauthenticated(client):
    res = client.get("/api/v1/users/me")

    assert res.status_code == 401
