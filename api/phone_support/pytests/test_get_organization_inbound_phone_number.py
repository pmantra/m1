from unittest import mock

import pytest

from models.enterprise import InboundPhoneNumber
from phone_support.service.phone_support import get_inbound_phone_number
from pytests.factories import EnterpriseUserFactory
from storage.connection import db
from utils.data import normalize_phone_number
from wallet.models.constants import WalletState


def test_get_inbound_phone_number__unauthorized(api_helpers, client, default_user):
    # When not passing authorized user in headers
    test_org_id = 1
    res = client.get(
        f"/api/v1/organization/{test_org_id}/inbound_phone_number?user_id={default_user.id}",
    )
    # Then
    assert res.status_code == 401


def test_get_inbound_phone_number__missing_query_param(
    api_helpers, client, default_user
):
    # When not passing user_id query param
    test_org_id = 1
    res = client.get(
        f"/api/v1/organization/{test_org_id}/inbound_phone_number",
        headers=api_helpers.standard_headers(default_user),
    )

    # Then
    assert res.status_code == 400
    res_data = api_helpers.load_json(res)
    assert res_data["message"] == "Missing required query parameter 'user_id'"


def test_get_inbound_phone_number__invalid_query_param(
    api_helpers, client, default_user
):
    # When passing an invalid user_id
    test_org_id = 1
    fake_user_id = default_user.id + 1
    res = client.get(
        f"/api/v1/organization/{test_org_id}/inbound_phone_number?user_id={fake_user_id}",
        headers=api_helpers.standard_headers(default_user),
    )

    # Then
    assert res.status_code == 400
    res_data = api_helpers.load_json(res)
    assert res_data["message"] == "Invalid 'user_id'"


@pytest.mark.parametrize(
    "fflag, is_wallet, phone_number, status_code",
    [
        (True, True, "5703024100", 200),
        (True, False, "5703024100", 204),
        (True, True, None, 204),
        (True, False, None, 204),
        (False, True, None, 204),
    ],
)
@mock.patch("phone_support.service.phone_support.should_include_inbound_phone_number")
@mock.patch(
    "wallet.services.reimbursement_wallet.ReimbursementWalletService.get_enrolled_wallets"
)
def test_get_inbound_phone_number__base_cases(
    mock_get_enrolled_wallets,
    mock_should_include_inbound_phone_number,
    fflag,
    is_wallet,
    phone_number,
    status_code,
    api_helpers,
    client,
    factories,
):
    # Given feature flag, member wallet status, member and org based on parameters
    mock_should_include_inbound_phone_number.return_value = fflag
    mock_get_enrolled_wallets.return_value = [] if not is_wallet else [1]
    user = factories.EnterpriseUserFactory.create()

    # Explicitly set organization property to be None, so we are force to use organization_v2 throughout endpoint flow
    user.user_organization_employees = []
    db.session.commit()

    if phone_number is not None:
        db_phone_number = InboundPhoneNumber(
            id=1, number=phone_number, organizations=[user.organization_v2]
        )
        db.session.add(db_phone_number)
        db.session.commit()
    # When
    res = client.get(
        f"/api/v1/organization/{user.organization_v2.id}/inbound_phone_number?user_id={user.id}",
        headers=api_helpers.standard_headers(user),
    )

    # Then
    assert res.status_code == status_code
    if status_code == 200:
        res_data = api_helpers.load_json(res)
        assert res_data["user_id"] == user.id
        assert res_data["organization_id"] == user.organization_v2.id
        if phone_number is not None:
            normalized, _ = normalize_phone_number(phone_number, None)
            assert res_data["inbound_phone_number"] == normalized
        else:
            assert res_data["inbound_phone_number"] == None


def test_get_inbound_phone_number__no_organization_in_url(
    api_helpers, client, default_user
):
    # Given: no organization in url
    # When
    res = client.get(
        f"/api/v1/organization/None/inbound_phone_number?user_id={default_user.id}",
        headers=api_helpers.standard_headers(default_user),
    )

    # Then
    assert res.status_code == 404


def test_get_inbound_phone_number__user_has_no_organization(
    api_helpers, client, default_user
):
    # Given: no organization on user
    test_org_id = 1
    # When
    res = client.get(
        f"/api/v1/organization/{test_org_id}/inbound_phone_number?user_id={default_user.id}",
        headers=api_helpers.standard_headers(default_user),
    )

    # Then
    assert res.status_code == 400
    res_data = api_helpers.load_json(res)
    assert res_data["message"] == "User does not have an organization"


def test_get_inbound_phone_number__org_doesnt_exist(api_helpers, client, factories):
    # Given - org that doesn't exist in DB
    test_org_id = 1
    user = factories.EnterpriseUserFactory.create()

    # When
    res = client.get(
        f"/api/v1/organization/{test_org_id}/inbound_phone_number?user_id={user.id}",
        headers=api_helpers.standard_headers(user),
    )

    # Then
    assert res.status_code == 400
    res_data = api_helpers.load_json(res)
    assert res_data["message"] == "Organization does not exist"


def test_get_inbound_phone_number__org_id_dont_match(api_helpers, client, factories):
    # Given - org ID that doesn't match org ID on user
    test_org = factories.OrganizationFactory.create(name="Slay Boots")
    user = factories.EnterpriseUserFactory.create()

    # When
    res = client.get(
        f"/api/v1/organization/{test_org.id}/inbound_phone_number?user_id={user.id}",
        headers=api_helpers.standard_headers(user),
    )

    # Then
    assert res.status_code == 400
    res_data = api_helpers.load_json(res)
    assert (
        res_data["message"]
        == "Given organization ID does not match user organization ID"
    )


@mock.patch("phone_support.service.phone_support.should_include_inbound_phone_number")
def test_get_inbound_phone_number_method__no_enrolled_wallets(
    mock_should_include_inbound_phone_number, enterprise_user
):
    mock_should_include_inbound_phone_number.return_value = True
    # given enterprise member with organization phone number
    member = enterprise_user
    member.organization_employee.json = {"wallet_enabled": True}
    db_phone_number = InboundPhoneNumber(
        id=1, number="5703024100", organizations=[member.organization]
    )
    db.session.add(db_phone_number)
    db.session.commit()

    # when we get phone number
    phone_number = get_inbound_phone_number(member)

    # then phone number shouldn't exist
    assert phone_number is None


@mock.patch("phone_support.service.phone_support.should_include_inbound_phone_number")
def test_get_inbound_phone_number_method__enrolled_wallets(
    mock_should_include_inbound_phone_number, factories
):
    mock_should_include_inbound_phone_number.return_value = True
    # given enterprise member with organization phone number and wallet
    member = EnterpriseUserFactory.create()
    member.organization_employee.json = {"wallet_enabled": True}
    member.organization.name = "Test Org"
    resource = factories.ResourceFactory()
    reimbursement_organization_settings = (
        factories.ReimbursementOrganizationSettingsFactory(
            organization_id=member.organization.id,
            benefit_faq_resource_id=resource.id,
            survey_url="fake_url",
        )
    )
    wallet = factories.ReimbursementWalletFactory.create(
        user_id=member.id,
        reimbursement_organization_settings_id=reimbursement_organization_settings.id,
        state=WalletState.QUALIFIED,
    )
    factories.ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=member.id,
    )

    db_phone_number = InboundPhoneNumber(
        id=1, number="5703024100", organizations=[member.organization]
    )
    db.session.add(db_phone_number)
    db.session.commit()

    # when we get phone number
    phone_number = get_inbound_phone_number(member)

    # then phone number should be returned
    assert phone_number == "tel:+1-570-302-4100"


@mock.patch("phone_support.service.phone_support.should_include_inbound_phone_number")
def test_get_inbound_phone_number_method__enrolled_wallets_no_org_phone(
    mock_should_include_inbound_phone_number, factories
):
    mock_should_include_inbound_phone_number.return_value = True
    # given enterprise member with NO organization phone number and wallet
    member = EnterpriseUserFactory.create()
    member.organization_employee.json = {"wallet_enabled": True}
    member.organization.name = "Test Org"
    resource = factories.ResourceFactory()
    reimbursement_organization_settings = (
        factories.ReimbursementOrganizationSettingsFactory(
            organization_id=member.organization.id,
            benefit_faq_resource_id=resource.id,
            survey_url="fake_url",
        )
    )
    wallet = factories.ReimbursementWalletFactory.create(
        user_id=member.id,
        reimbursement_organization_settings_id=reimbursement_organization_settings.id,
        state=WalletState.QUALIFIED,
    )
    factories.ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=member.id,
    )

    # when we get phone number
    phone_number = get_inbound_phone_number(member)

    # then phone number shouldn't exist
    assert phone_number is None
