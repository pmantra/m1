from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from braze import BrazeUserAttributes
from models.enterprise import Invite, InviteType, OnboardingState
from models.tracks import TrackName


@pytest.fixture(scope="function", autouse=True)
def org_email_domain(factories):
    org = factories.OrganizationFactory.create(
        name="Maven Clinic",
        allowed_tracks=[*TrackName],
    )
    return factories.OrganizationEmailDomainFactory.create(
        domain="mavenclinic.com",
        organization=org,
    )


def test_create_fileless_invite_for_invalid_email_domain(
    client, api_helpers, default_user
):
    """
    Given
        - A fileless user is going through onboarding
    When
        - The user requests a fileless invite
        - The request contains an e-mail with an invalid domain
    Then
        - No new invite is created
        - The response contains a 403 status code
    """

    assert default_user.onboarding_state is None

    res = client.post(
        "/api/v1/fileless_invite",
        json={"company_email": "test@invalid.com", "is_employee": True},
        headers=api_helpers.standard_headers(default_user),
    )

    json = api_helpers.load_json(res)
    invite_count_for_user = Invite.query.filter(
        Invite.created_by_user_id == default_user.id
    ).count()
    assert res.status_code == 403
    assert json["errors"][0]["code"] == "INVALID_EMAIL_DOMAIN"
    assert invite_count_for_user == 0
    assert default_user.onboarding_state is None


def test_create_fileless_invite_already_exists_same_email(
    client, api_helpers, default_user, factories
):
    """
    Given
        - A user has an existing unclaimed invite
    When
        - The user requests a fileless invite
        - The request contains the email that matches the email for the existing invite
    Then
        - No new invite is created
        - The response contains a 201 status code
    """
    factories.UserOnboardingStateFactory.create(
        user=default_user, state=OnboardingState.FILELESS_INVITED_EMPLOYEE
    )
    factories.InviteFactory.create(
        created_by_user=default_user,
        email="test@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
    )

    res = client.post(
        "/api/v1/fileless_invite",
        json={"company_email": "test@mavenclinic.com", "is_employee": True},
        headers=api_helpers.standard_headers(default_user),
    )

    assert res.status_code == 201
    assert (
        default_user.onboarding_state.state == OnboardingState.FILELESS_INVITED_EMPLOYEE
    )


def test_create_fileless_invite_already_exists_different_email(
    client, api_helpers, default_user, factories
):
    """
    Given
        - A user has an existing unclaimed invite
    When
        - The user requests a fileless invite
        - The request contains a different email from the one in the existing invite
    Then
        - A new invite is not created
        - Existing invite is updated with the new email
        - The response contains a 201 status code
    """

    factories.UserOnboardingStateFactory.create(
        user=default_user, state=OnboardingState.FILELESS_INVITED_EMPLOYEE
    )
    invite = factories.InviteFactory.create(
        created_by_user=default_user,
        email="first@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
    )

    res = client.post(
        "/api/v1/fileless_invite",
        json={"company_email": "second@mavenclinic.com", "is_employee": True},
        headers=api_helpers.standard_headers(default_user),
    )

    assert res.status_code == 201
    assert invite.email == "second@mavenclinic.com"


def test_create_fileless_invite(client, api_helpers, default_user, factories):
    """
    Given
        - A fileless user is going through the onboarding flow
    When
        - The user requests a fileless invite
    Then
        - A new invite is created
        - The user's onboarding status is changed
        - The response contains a 201 status code
    """

    factories.UserOnboardingStateFactory.create(
        user=default_user, state=OnboardingState.USER_CREATED
    )

    res = client.post(
        "/api/v1/fileless_invite",
        json={"company_email": "test@mavenclinic.com", "is_employee": True},
        headers=api_helpers.standard_headers(default_user),
    )

    assert res.status_code == 201
    assert (
        default_user.onboarding_state.state == OnboardingState.FILELESS_INVITED_EMPLOYEE
    )


def test_create_fileless_invite_dependent(client, api_helpers, default_user, factories):
    """
    Given
        - A dependent of a fileless user is going through the onboarding flow
    When
        - The dependent requests a fileless invite
    Then
        - A new invite is created
        - The dependent's onboarding status is changed
        - The response contains a 201 status code
    """

    factories.UserOnboardingStateFactory.create(
        user=default_user, state=OnboardingState.USER_CREATED
    )

    res = client.post(
        "/api/v1/fileless_invite",
        json={"company_email": "test@mavenclinic.com", "is_employee": False},
        headers=api_helpers.standard_headers(default_user),
    )

    assert res.status_code == 201
    assert (
        default_user.onboarding_state.state
        == OnboardingState.FILELESS_INVITED_DEPENDENT
    )


def test_create_fileless_invite_not_already_claimed(
    client, api_helpers, default_user, factories
):
    """
    Given
        - A user has an existing unclaimed invite
    When
        - The user requests a fileless invite
    Then
        - No new invite is created
        - The response contains a 201 status code
    """

    default_user.health_profile.birthday = date(2000, 1, 1)
    factories.UserOnboardingStateFactory.create(
        user=default_user, state=OnboardingState.FILELESS_INVITED_EMPLOYEE
    )
    factories.InviteFactory.create(
        created_by_user=default_user,
        email="test@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
        claimed=False,
    )

    assert Invite.query.count() == 1

    res = client.post(
        "/api/v1/fileless_invite",
        json={"company_email": "test@mavenclinic.com", "is_employee": True},
        headers=api_helpers.standard_headers(default_user),
    )

    assert res.status_code == 201
    assert (
        default_user.onboarding_state.state == OnboardingState.FILELESS_INVITED_EMPLOYEE
    )

    assert Invite.query.count() == 1


def test_create_fileless_invite_already_claimed(
    client, api_helpers, default_user, factories
):
    """
    Given
        - A user has an existing claimed invite
    When
        - The user requests a fileless invite
    Then
        - A new invite is created
        - The response contains a 201 status code
    """

    default_user.health_profile.birthday = date(2000, 1, 1)
    factories.UserOnboardingStateFactory.create(
        user=default_user, state=OnboardingState.FILELESS_INVITED_EMPLOYEE
    )
    factories.InviteFactory.create(
        created_by_user=default_user,
        email="test@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
        claimed=True,
    )

    assert Invite.query.count() == 1

    res = client.post(
        "/api/v1/fileless_invite",
        json={"company_email": "test@mavenclinic.com", "is_employee": True},
        headers=api_helpers.standard_headers(default_user),
    )

    assert res.status_code == 201
    assert (
        default_user.onboarding_state.state == OnboardingState.FILELESS_INVITED_EMPLOYEE
    )

    assert Invite.query.count() == 2


def test_create_fileless_invite_with_expired_invite(
    client, api_helpers, default_user, factories
):
    """
    Given
        - A user has an existing unclaimed but expired invite
    When
        - The user requests a fileless invite
    Then
        - A new invite is created
        - The response contains a 201 status code
    """

    default_user.health_profile.birthday = date(2000, 1, 1)
    factories.UserOnboardingStateFactory.create(
        user=default_user, state=OnboardingState.FILELESS_INVITED_EMPLOYEE
    )
    factories.InviteFactory.create(
        created_by_user=default_user,
        email="test@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
        claimed=False,
        expires_at=datetime.now() - timedelta(days=2),
    )

    assert Invite.query.count() == 1

    res = client.post(
        "/api/v1/fileless_invite",
        json={"company_email": "test@mavenclinic.com", "is_employee": True},
        headers=api_helpers.standard_headers(default_user),
    )

    assert res.status_code == 201
    assert (
        default_user.onboarding_state.state == OnboardingState.FILELESS_INVITED_EMPLOYEE
    )

    assert Invite.query.count() == 2


def test_claim_fileless_invite_invalid(client, api_helpers, default_user, factories):
    """
    Given
        - A user has an existing invite
    When
        - The user attempts to claim the existing invite using an invalid id
    Then
        - No new invite is created
        - The response contains a 404 status code
    """

    factories.UserOnboardingStateFactory.create(
        user=default_user, state=OnboardingState.FILELESS_INVITED_EMPLOYEE
    )

    res = client.post(
        "/api/v1/fileless_invite/claim",
        json={"invite_id": "INVALID"},
        headers=api_helpers.standard_headers(default_user),
    )

    json = api_helpers.load_json(res)
    assert res.status_code == 404
    assert json["errors"][0]["code"] == "FILELESS_INVITE_INVALID"
    assert (
        default_user.onboarding_state.state == OnboardingState.FILELESS_INVITED_EMPLOYEE
    )


def test_claim_fileless_invite_already_claimed(
    client, api_helpers, default_user, factories
):
    """
    Given
        - A user has an existing claimed invite
    When
        - The user attempts to claim an already claimed invite
    Then
        - No new invite is created
        - The response contains a 400 status code
    """

    factories.UserOnboardingStateFactory.create(
        user=default_user, state=OnboardingState.FILELESS_INVITED_EMPLOYEE
    )
    invite = factories.InviteFactory.create(
        created_by_user=default_user,
        email="test@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
        claimed=True,
    )

    res = client.post(
        "/api/v1/fileless_invite/claim",
        json={"invite_id": invite.id},
        headers=api_helpers.standard_headers(default_user),
    )

    json = api_helpers.load_json(res)
    assert res.status_code == 400
    assert json["errors"][0]["code"] == "FILELESS_INVITE_ALREADY_CLAIMED"
    assert (
        default_user.onboarding_state.state == OnboardingState.FILELESS_INVITED_EMPLOYEE
    )


def test_claim_fileless_invite_expired(client, api_helpers, default_user, factories):
    """
    Given
        - A user has an existing unclaimed but expired invite
    When
        - The user attempts to claim the invite
    Then
        - No new invite is created
        - The response contains a 410 status code
    """

    factories.UserOnboardingStateFactory.create(
        user=default_user, state=OnboardingState.FILELESS_INVITED_EMPLOYEE
    )
    invite = factories.InviteFactory.create(
        created_by_user=default_user,
        email="test@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
        claimed=False,
        expires_at=datetime.now() - timedelta(days=2),
    )

    res = client.post(
        "/api/v1/fileless_invite/claim",
        json={"invite_id": invite.id},
        headers=api_helpers.standard_headers(default_user),
    )

    json = api_helpers.load_json(res)
    assert res.status_code == 410
    assert json["errors"][0]["code"] == "FILELESS_INVITE_EXPIRED"
    assert (
        default_user.onboarding_state.state == OnboardingState.FILELESS_INVITED_EMPLOYEE
    )


def test_claim_fileless_invite_invalid_date_of_birth(
    client, api_helpers, default_user, factories
):
    """
    Given
        - A user has an existing unclaimed invite
    When
        - The user attempts to claim but user health profile has missing birthday
    Then
        - No new invite is created
        - The response contains a 400 status code
    """
    default_user.health_profile.birthday = None
    factories.UserOnboardingStateFactory.create(
        user=default_user, state=OnboardingState.FILELESS_INVITED_EMPLOYEE
    )
    invite = factories.InviteFactory.create(
        created_by_user=default_user,
        email="test@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
        claimed=False,
    )

    res = client.post(
        "/api/v1/fileless_invite/claim",
        json={"invite_id": invite.id},
        headers=api_helpers.standard_headers(default_user),
    )

    json = api_helpers.load_json(res)
    assert res.status_code == 400
    assert json["errors"][0]["code"] == "FILELESS_INVITE_INVALID_DATE_OF_BIRTH"
    assert (
        default_user.onboarding_state.state == OnboardingState.FILELESS_INVITED_EMPLOYEE
    )


@patch("braze.client.BrazeClient.track_user")
def test_claim_fileless_invite(
    mock_track_user, client, api_helpers, default_user, factories
):
    """
    Given
        - A user has an existing unclaimed invite
    When
        - The user attempts to claim the invite
    Then
        - The invite is marked as claimed
        - The user's onboarding status is updated to Track Selection
        - Braze is updated to reflect a claimed account and marking the user as an employee
        - A 204 status code is returned
    """

    default_user.health_profile.birthday = date(2000, 1, 1)
    factories.UserOnboardingStateFactory.create(
        user=default_user, state=OnboardingState.FILELESS_INVITED_EMPLOYEE
    )
    invite = factories.InviteFactory.create(
        created_by_user=default_user,
        email="test@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
        claimed=False,
    )

    res = client.post(
        "/api/v1/fileless_invite/claim",
        json={"invite_id": invite.id},
        headers=api_helpers.standard_headers(default_user),
    )

    expected_user_attributes = BrazeUserAttributes(
        external_id=invite.id,
        attributes={
            "email": invite.email,
            "first_name": invite.name,
            "invite_id": invite.id,
            "invite_time": invite.created_at.isoformat(),
            "account_claimed": True,
            "is_employee": True,
            "type": "FILELESS",
        },
    )
    mock_track_user.assert_called_with(
        user_attributes=expected_user_attributes,
    )
    assert res.status_code == 204
    assert invite.claimed is True
    assert default_user.onboarding_state.state == OnboardingState.TRACK_SELECTION
    assert default_user.organization_employee is not None


def test_claim_fileless_invite_guarantor_and_spouse(client, api_helpers, factories):
    """
    Given
        - A user has gone through onboarding up to requesting a fileless invite
    When
        - Both a user (employee) and their dependent attempt to claim invites
    Then
        - A 204 response is returned for each
        - The dependent's OrganizationEmployee has a filled out dependent_id field
        - The user's OrganizationEmployee does not have a filled out dependent_id field
        - User's and dependent's onboarding state's are updated to Track Selection
    """

    guarantor = factories.DefaultUserFactory.create(email="test@mavenclinic.com")
    guarantor.health_profile.birthday = date(2000, 1, 1)
    factories.UserOnboardingStateFactory.create(
        user=guarantor, state=OnboardingState.FILELESS_INVITED_EMPLOYEE
    )
    guarantor_invite = factories.InviteFactory.create(
        created_by_user=guarantor,
        email=guarantor.email,
        name=guarantor.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
        claimed=False,
    )

    spouse = factories.DefaultUserFactory.create()
    spouse.health_profile.birthday = date(2000, 2, 2)
    factories.UserOnboardingStateFactory.create(
        user=spouse, state=OnboardingState.FILELESS_INVITED_DEPENDENT
    )
    spouse_invite = factories.InviteFactory.create(
        created_by_user=spouse,
        email=guarantor.email,
        name=spouse.first_name,
        type=InviteType.FILELESS_DEPENDENT,
        claimed=False,
    )

    guarantor_res = client.post(
        "/api/v1/fileless_invite/claim",
        json={"invite_id": guarantor_invite.id},
        headers=api_helpers.standard_headers(guarantor),
    )
    spouse_res = client.post(
        "/api/v1/fileless_invite/claim",
        json={"invite_id": spouse_invite.id},
        headers=api_helpers.standard_headers(spouse),
    )

    guarantor_emp = guarantor.organization_employee
    spouse_emp = spouse.organization_employee

    assert guarantor_res.status_code == 204
    assert spouse_res.status_code == 204
    assert guarantor_invite.claimed is True
    assert spouse_invite.claimed is True
    assert guarantor.onboarding_state.state == OnboardingState.TRACK_SELECTION
    assert spouse.onboarding_state.state == OnboardingState.TRACK_SELECTION
    assert "AUTOGEN" in guarantor_emp.unique_corp_id
    assert guarantor_emp.unique_corp_id == spouse_emp.unique_corp_id
    assert guarantor_emp.dependent_id == ""
    assert "AUTOGEN" in spouse_emp.dependent_id


def test_claim_fileless_invite_existing_employee(
    client, api_helpers, default_user, org_email_domain, factories
):
    """
    Given
        - A user already has an OrganizationEmployee with an e-mail matching the invite

    When
        - A user attempts to claim the invite

    Then
        - The user's onboarding status is updated to Track Selection
        - The invite is marked as claimed
        - A 204 status code is returned
    """

    default_user.health_profile.birthday = date(2000, 1, 1)
    factories.UserOnboardingStateFactory.create(
        user=default_user, state=OnboardingState.FILELESS_INVITED_EMPLOYEE
    )
    invite = factories.InviteFactory.create(
        created_by_user=default_user,
        email="test@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
        claimed=False,
    )
    existing_emp = factories.OrganizationEmployeeFactory.create(
        email=invite.email,
        date_of_birth=default_user.health_profile.birthday,
        organization=org_email_domain.organization,
    )

    res = client.post(
        "/api/v1/fileless_invite/claim",
        json={"invite_id": invite.id},
        headers=api_helpers.standard_headers(default_user),
    )

    assert res.status_code == 204
    assert default_user.organization_employee is existing_emp
    assert invite.claimed is True
    assert default_user.onboarding_state.state == OnboardingState.TRACK_SELECTION
