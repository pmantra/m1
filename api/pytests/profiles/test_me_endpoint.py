from datetime import date, datetime, timedelta
from unittest import mock

import pytest
from flask.testing import FlaskClient

from authn.domain.service.mfa import MFAEnforcementReason
from authn.models.user import User
from models.enterprise import InviteType, OnboardingState
from models.profiles import AgreementNames
from models.tracks import TrackName
from pytests.freezegun import freeze_time
from storage.connection import db
from utils.api_interaction_mixin import APIInteractionMixin


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_me_no_onboarding_state(client, api_helpers, default_user):
    # When
    res = client.get("/api/v1/me", headers=api_helpers.standard_headers(default_user))
    # Then
    json = api_helpers.load_json(res)
    assert res.status_code == 200
    assert json["onboarding_state"] is None


@pytest.mark.usefixtures("patch_user_id_encoded_token")
@pytest.mark.parametrize(
    argnames="state", argvalues=[state for state in OnboardingState]
)
def test_me_onboarding_state(client, api_helpers, default_user, factories, state):
    # Given
    factories.UserOnboardingStateFactory.create(user=default_user, state=state)
    # When
    res = client.get("/api/v1/me", headers=api_helpers.standard_headers(default_user))
    # Then
    json = api_helpers.load_json(res)
    assert res.status_code == 200
    assert json["onboarding_state"] == state.value


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_me_invite(client, api_helpers, default_user, factories):
    # Given
    invite = factories.InviteFactory.create(
        created_by_user=default_user,
        email="first@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
    )
    # When
    res = client.get("/api/v1/me", headers=api_helpers.standard_headers(default_user))
    # Then
    json = api_helpers.load_json(res)
    assert res.status_code == 200
    assert json["unclaimed_invite"]["invite_id"] == invite.id
    assert json["unclaimed_invite"]["type"] == InviteType.FILELESS_EMPLOYEE.value
    assert json["unclaimed_invite"]["email"] == "first@mavenclinic.com"


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_me_multiple_invites(client, api_helpers, default_user, factories):
    # Given
    factories.InviteFactory.create(
        created_by_user=default_user,
        email="first@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
        claimed=True,
    )

    invite_2 = factories.InviteFactory.create(
        created_by_user=default_user,
        email="first@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
    )
    # When
    res = client.get("/api/v1/me", headers=api_helpers.standard_headers(default_user))
    # Then
    json = api_helpers.load_json(res)
    assert res.status_code == 200
    assert json["unclaimed_invite"]["invite_id"] == invite_2.id
    assert json["unclaimed_invite"]["type"] == InviteType.FILELESS_EMPLOYEE.value
    assert json["unclaimed_invite"]["email"] == "first@mavenclinic.com"


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_me_multiple_unclaimed_invites(client, api_helpers, default_user, factories):
    # Given
    with freeze_time(datetime.now() - timedelta(hours=1)):
        factories.InviteFactory.create(
            created_by_user=default_user,
            email="first@mavenclinic.com",
            name=default_user.first_name,
            type=InviteType.FILELESS_EMPLOYEE,
        )

    invite_2 = factories.InviteFactory.create(
        created_by_user=default_user,
        email="first@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
    )

    # When
    res = client.get("/api/v1/me", headers=api_helpers.standard_headers(default_user))
    # Then
    json = api_helpers.load_json(res)
    assert res.status_code == 200
    assert json["unclaimed_invite"]["invite_id"] == invite_2.id
    assert json["unclaimed_invite"]["type"] == InviteType.FILELESS_EMPLOYEE.value
    assert json["unclaimed_invite"]["email"] == "first@mavenclinic.com"


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_me_no_unclaimed_invites(client, api_helpers, default_user, factories):
    # Given
    factories.InviteFactory.create(
        created_by_user=default_user,
        email="first@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
        claimed=True,
    )
    # When
    res = client.get("/api/v1/me", headers=api_helpers.standard_headers(default_user))
    # Then
    json = api_helpers.load_json(res)
    assert res.status_code == 200
    assert json["unclaimed_invite"] is None


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_passthrough_stratgegy_serves_default_flags(
    ff_test_data, client, api_helpers, default_user, logs
):
    # Given
    ff_test_data.update(
        ff_test_data.flag("configure-flagr-stubs-me-endpoint").value_for_all(
            {"strategy": "passthrough"}
        )
    )
    log_msg = "The served Flagr stubs strategy is no longer supported. Serving default stubs instead."
    # When
    res = client.get("/api/v1/me", headers=api_helpers.standard_headers(default_user))
    log = next((r for r in logs if log_msg in r["event"]), None)
    # Then
    assert res.status_code == 200
    assert log is not None


def test_stubbed_flags(ff_test_data, client, api_helpers, default_user):
    # Given
    ff_test_data.update(
        ff_test_data.flag("configure-flagr-stubs-me-endpoint").value_for_all(
            {
                "strategy": "stub",
                "stubs": {"f1": "v1", "f2": "v2"},
            }
        )
    )
    # When
    res = client.get("/api/v1/me", headers=api_helpers.standard_headers(default_user))
    json = api_helpers.load_json(res)
    # Then
    assert res.status_code == 200
    assert json["flags"] == {"f1": "v1", "f2": "v2"}


def test_no_date_of_birth(client, api_helpers, default_user):
    res = client.get("/api/v1/me", headers=api_helpers.standard_headers(default_user))
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json["date_of_birth"] is None


def test_date_of_birth(client, api_helpers, default_user, factories):
    factories.HealthProfileFactory.create(
        user=default_user, birthday=datetime.strptime("2000-01-01", "%Y-%m-%d")
    )

    res = client.get("/api/v1/me", headers=api_helpers.standard_headers(default_user))
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json["date_of_birth"] == "2000-01-01"


def test_no_created_at_returned(client, api_helpers, default_user):
    res = client.get("/api/v1/me", headers=api_helpers.standard_headers(default_user))
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert "created_at" not in json


def test_me_with_tracks(client, api_helpers, default_user, factories):
    # Given
    factories.MemberTrackFactory.create(
        user=default_user,
        ended_at=datetime.today() - timedelta(days=800),
    )
    factories.MemberTrackFactory.create(
        user=default_user,
        ended_at=datetime.today() - timedelta(days=400),
    )
    factories.MemberTrackFactory.create(
        user=default_user,
    )
    factories.MemberTrackFactory.create(
        user=default_user, start_date=date.today() + timedelta(weeks=2)
    ).activated_at = None

    db.session.refresh(default_user)
    # When
    res = client.get("/api/v1/me", headers=api_helpers.standard_headers(default_user))

    # Then
    json = api_helpers.load_json(res)
    inactive_tracks = json["inactive_tracks"]
    active_tracks = json["active_tracks"]
    scheduled_tracks = json["scheduled_tracks"]

    assert res.status_code == 200

    assert len(inactive_tracks) == 2
    assert "ended_at" in inactive_tracks[0]

    assert len(active_tracks) == 1
    assert "ended_at" not in active_tracks[0]

    assert len(scheduled_tracks) == 1
    assert "start_date" in scheduled_tracks[0]


def test_me_pending_agreements(client, api_helpers, enterprise_user, factories):
    # Given
    eng = factories.LanguageFactory.create(name="English")

    factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
        language=eng,
    )

    org_agreement_v1 = factories.AgreementFactory.create(
        name=AgreementNames.CHEESECAKE_FACTORY,
        version=1,
        language=eng,
    )
    org_agreement_v2 = factories.AgreementFactory.create(
        name=AgreementNames.CHEESECAKE_FACTORY,
        version=2,
        language=eng,
    )
    other_org = factories.OrganizationFactory.create()
    factories.OrganizationAgreementFactory.create(
        organization=enterprise_user.organization, agreement=org_agreement_v1
    )
    factories.OrganizationAgreementFactory.create(
        organization=other_org, agreement=org_agreement_v1
    )
    factories.OrganizationAgreementFactory.create(
        organization=enterprise_user.organization, agreement=org_agreement_v2
    )
    factories.OrganizationAgreementFactory.create(
        organization=other_org, agreement=org_agreement_v2
    )

    # When
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
        return_value={enterprise_user.organization_v2.id},
    ):
        res = client.get(
            "/api/v1/me", headers=api_helpers.standard_headers(enterprise_user)
        )

    # Then
    json = api_helpers.load_json(res)
    pending_agreements = json["pending_agreements"]
    organization_all_pending_agreements = json["all_pending_agreements"]["organization"]
    user_all_pending_agreements = json["all_pending_agreements"]["user"]

    assert res.status_code == 200

    assert len(pending_agreements) == 1
    assert len(organization_all_pending_agreements) == 1
    assert len(user_all_pending_agreements) == 1


def test_mfa_enforcement_info(client, api_helpers, default_user, mock_mfa_service):
    # Given
    mock_mfa_service.get_user_mfa_status.return_value = (
        False,
        MFAEnforcementReason.NOT_REQUIRED,
    )

    # When
    res = client.get("/api/v1/me", headers=api_helpers.standard_headers(default_user))

    # Then
    json = api_helpers.load_json(res)
    assert res.status_code == 200
    assert json["mfa_enforcement_info"]["require_mfa"] is False
    assert json["mfa_enforcement_info"]["mfa_enforcement_reason"] == "NOT_REQUIRED"


@pytest.mark.parametrize(
    argnames="exclude_args,expected_excluded_fields",
    argvalues=[
        (
            "?exclude=agreements&exclude=tracks",
            (
                "pending_agreements",
                "all_pending_agreements",
                "active_tracks",
                "inactive_tracks",
                "scheduled_tracks",
            ),
        ),
        (
            "?exclude=care_coordinators&exclude=mfa",
            (
                "care_coordinators",
                "mfa_enforcement_info",
            ),
        ),
        (
            "?exclude=organization",
            ("organization",),
        ),
        (
            "?exclude=unclaimed_invite&exclude=wallet",
            ("unclaimed_invite", "wallet"),
        ),
        (
            "?exclude=deprecated&exclude=flags&exclude=profiles&include_profile=true",
            (
                "country",
                "flags",
                "has_available_tracks",
                "subscription_plans",
                "test_group",
                "use_alegeus_for_reimbursements",
                "profiles",
            ),
        ),
        (
            "?exclude=user",
            (
                "id",
                "email",
                "first_name",
                "middle_name",
                "last_name",
                "name",
                "username",
                "date_of_birth",
                "role",
                "onboarding_state",
                "avatar_url",
                "image_url",
                "image_id",
                "esp_id",
                "encoded_id",
                "mfa_state",
                "sms_phone_number",
                "bright_jwt",
            ),
        ),
    ],
)
def test_excludes_fields(
    client, api_helpers, default_user, exclude_args, expected_excluded_fields
):
    res = client.get(
        f"/api/v1/me{exclude_args}",
        headers=api_helpers.standard_headers(default_user),
    )

    json = api_helpers.load_json(res)
    assert res.status_code == 200

    for expected_excluded_field in expected_excluded_fields:
        assert expected_excluded_field not in json


@pytest.mark.parametrize(
    argnames="include_only_args,expected_included_fields",
    argvalues=[
        (
            "?include_only=agreements&include_only=tracks",
            (
                "pending_agreements",
                "all_pending_agreements",
                "active_tracks",
                "inactive_tracks",
                "scheduled_tracks",
            ),
        ),
        (
            "?include_only=care_coordinators&include_only=mfa",
            (
                "care_coordinators",
                "mfa_enforcement_info",
            ),
        ),
        (
            "?include_only=organization",
            ("organization",),
        ),
        (
            "?include_only=unclaimed_invite&include_only=wallet",
            ("unclaimed_invite", "wallet"),
        ),
        (
            # `include_only` should take precedence
            "?include_only=unclaimed_invite&exclude=unclaimed_invite&include_profile=true",
            ("unclaimed_invite",),
        ),
        (
            "?include_only=deprecated&include_only=flags&include_only=profiles&include_profile=true",
            (
                "country",
                "flags",
                "has_available_tracks",
                "subscription_plans",
                "test_group",
                "use_alegeus_for_reimbursements",
                "profiles",
            ),
        ),
        (
            "?include_only=user",
            (
                "id",
                "email",
                "first_name",
                "middle_name",
                "last_name",
                "name",
                "username",
                "date_of_birth",
                "role",
                "onboarding_state",
                "avatar_url",
                "image_url",
                "image_id",
                "esp_id",
                "encoded_id",
                "bright_jwt",
                "mfa_state",
                "sms_phone_number",
            ),
        ),
    ],
)
def test_includes_only_specific_fields(
    client, api_helpers, default_user, include_only_args, expected_included_fields
):
    res = client.get(
        f"/api/v1/me{include_only_args}",
        headers=api_helpers.standard_headers(default_user),
    )

    json = api_helpers.load_json(res)
    assert res.status_code == 200

    assert len(json) == len(expected_included_fields)
    for expected_included_field in expected_included_fields:
        assert expected_included_field in json


@pytest.mark.parametrize(
    "track_name, expected_dashboard",
    [
        (TrackName.PREGNANCY, "dashboard2020"),
        (TrackName.PARENTING_AND_PEDIATRICS, "dashboard2020"),
    ],
)
def test_me_dashboard_variations(
    client: FlaskClient,
    api_helpers: APIInteractionMixin,
    default_user: User,
    factories,
    mock_mfa_service,
    track_name: TrackName,
    expected_dashboard: str,
):
    factories.MemberTrackFactory.create(name=track_name, user=default_user)
    mock_mfa_service.get_user_mfa_status.return_value = (
        False,
        MFAEnforcementReason.NOT_REQUIRED,
    )

    response = client.get(
        "/api/v1/me", headers=api_helpers.standard_headers(default_user)
    )

    json = api_helpers.load_json(response)
    assert json["active_tracks"][0]["dashboard"] == expected_dashboard


@pytest.mark.parametrize("benefits_url", ["testurl.com", None])
def test_organization__benefits_url(benefits_url, factories, client, api_helpers):

    # Given
    organization = factories.OrganizationFactory.create(
        id=1,
        name="ABC International",
        US_restricted=False,
        benefits_url=benefits_url,
    )

    member = factories.MemberFactory.create()
    factories.MemberTrackFactory.create(
        name=TrackName.PREGNANCY,
        user=member,
        client_track=factories.ClientTrackFactory(organization=organization),
        current_phase="week-15",
    )

    # When
    res = client.get("/api/v1/me", headers=api_helpers.standard_headers(member))

    # Then
    json = api_helpers.load_json(res)
    organization = json["organization"]

    assert organization["benefits_url"] == benefits_url
