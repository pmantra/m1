import datetime
from unittest import mock
from unittest.mock import patch

import pytest

from pytests.factories import EnterpriseUserFactory, ReimbursementWalletUsersFactory
from wallet.models.constants import (
    AllowedMembers,
    FertilityProgramTypes,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.pytests.factories import WalletUserInviteFactory
from wallet.pytests.wallet.resources.conftest import shareable_wallet  # noqa: F401
from wallet.pytests.wallet.resources.test_post_invitation_decision import (  # noqa: F401
    shareable_wallet_and_user,
)
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository
from wallet.resources.reimbursement_wallet_dashboard import CanApplyForWalletResult

DUMMY_ROS = ReimbursementOrganizationSettings(
    id=0,
    organization_id=1,
    benefit_overview_resource_id=2,
    benefit_faq_resource_id=3,
    survey_url="survey_url",
    required_module_id=4,
    started_at=datetime.datetime.utcnow(),
    ended_at=datetime.datetime.utcnow(),
    taxation_status=None,
    debit_card_enabled=False,
    direct_payment_enabled=False,
    rx_direct_payment_enabled=False,
    deductible_accumulation_enabled=False,
    closed_network=False,
    fertility_program_type=FertilityProgramTypes.CARVE_OUT,
    fertility_requires_diagnosis=False,
    fertility_allows_taxable=False,
    payments_customer_id=None,
    allowed_members=AllowedMembers.SINGLE_ANY_USER,
    name="name",
)


def test_get_wallet_user_info_happy_path_no_other_conditions(
    client,
    api_helpers,
    enterprise_user,
):
    with patch(
        "wallet.resources.wallet_user_info.get_eligible_wallet_org_settings",
    ) as eligibility_settings_mock:
        eligibility_settings_mock.return_value = [DUMMY_ROS]
        res = client.get(
            "/api/v1/-/reimbursement_wallet/application/user_info",
            headers=api_helpers.json_headers(enterprise_user),
        )
        eligibility_settings_mock.assert_called_once()
        eligibility_settings_mock.assert_called_with(
            enterprise_user.id,
            e9y_svc=mock.ANY,
            filter_out_existing_wallets=False,
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {
        "allow_application": True,
        "reimbursement_organization_settings_id": str(DUMMY_ROS.id),
        "existing_wallet_id": None,
        "existing_wallet_state": None,
        "is_share_a_wallet": False,
    }


@pytest.mark.parametrize(
    argnames=(
        "can_apply_for_wallet_mock_value",
        "expected_allow_application_value",
    ),
    argvalues=(
        (CanApplyForWalletResult(True, False), True),
        (CanApplyForWalletResult(False, False), False),
    ),
)
def test_get_wallet_user_info_happy_path_org_settings(
    client,
    api_helpers,
    enterprise_user,
    can_apply_for_wallet_mock_value,
    expected_allow_application_value,
):
    with patch(
        "wallet.resources.wallet_user_info.get_eligible_wallet_org_settings"
    ) as eligibility_settings_mock, patch(
        "wallet.resources.wallet_user_info.can_apply_for_wallet"
    ) as can_apply_for_wallet_mock:
        eligibility_settings_mock.return_value = [DUMMY_ROS]
        can_apply_for_wallet_mock.return_value = can_apply_for_wallet_mock_value
        res = client.get(
            "/api/v1/-/reimbursement_wallet/application/user_info",
            headers=api_helpers.json_headers(enterprise_user),
        )
        eligibility_settings_mock.assert_called_once()
        eligibility_settings_mock.assert_called_with(
            enterprise_user.id,
            e9y_svc=mock.ANY,
            filter_out_existing_wallets=False,
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {
        "allow_application": expected_allow_application_value,
        "reimbursement_organization_settings_id": str(DUMMY_ROS.id),
        "existing_wallet_id": None,
        "existing_wallet_state": None,
        "is_share_a_wallet": False,
    }


def test_get_wallet_user_info_no_org_settings(
    client,
    api_helpers,
    enterprise_user,
):
    with patch(
        "wallet.resources.wallet_user_info.get_eligible_wallet_org_settings",
    ) as eligibility_settings_mock:
        eligibility_settings_mock.return_value = []
        res = client.get(
            "/api/v1/-/reimbursement_wallet/application/user_info",
            headers=api_helpers.json_headers(enterprise_user),
        )
        eligibility_settings_mock.assert_called_once()
        eligibility_settings_mock.assert_called_with(
            enterprise_user.id,
            e9y_svc=mock.ANY,
            filter_out_existing_wallets=False,
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {
        "allow_application": False,
        "reimbursement_organization_settings_id": "",
        "existing_wallet_id": None,
        "existing_wallet_state": None,
        "is_share_a_wallet": False,
    }


def test_get_wallet_user_info_multiple_org_settings(
    client,
    api_helpers,
    enterprise_user,
):
    # In practice, we should never get multiple org settings
    other_org = ReimbursementOrganizationSettings(
        id=45,
        organization_id=1,
        benefit_overview_resource_id=2,
        benefit_faq_resource_id=3,
        survey_url="survey_url",
        required_module_id=4,
        started_at=datetime.datetime.utcnow(),
        ended_at=datetime.datetime.utcnow(),
        taxation_status=None,
        debit_card_enabled=False,
        direct_payment_enabled=True,
        rx_direct_payment_enabled=False,
        deductible_accumulation_enabled=True,
        closed_network=False,
        fertility_program_type=FertilityProgramTypes.CARVE_OUT,
        fertility_requires_diagnosis=False,
        fertility_allows_taxable=False,
        payments_customer_id=None,
        allowed_members=AllowedMembers.SINGLE_ANY_USER,
        name="name",
    )
    with patch(
        "wallet.resources.wallet_user_info.get_eligible_wallet_org_settings",
    ) as eligibility_settings_mock:
        eligibility_settings_mock.return_value = [other_org, DUMMY_ROS]
        res = client.get(
            "/api/v1/-/reimbursement_wallet/application/user_info",
            headers=api_helpers.json_headers(enterprise_user),
        )
        eligibility_settings_mock.assert_called_once()
        eligibility_settings_mock.assert_called_with(
            enterprise_user.id,
            e9y_svc=mock.ANY,
            filter_out_existing_wallets=False,
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {
        "allow_application": True,
        # Use the first org id in the list.
        "reimbursement_organization_settings_id": str(other_org.id),
        "existing_wallet_id": None,
        "existing_wallet_state": None,
        "is_share_a_wallet": False,
    }


@pytest.mark.parametrize(
    argnames=("allow_application", "state", "rwu_status", "wallet_user_type"),
    argvalues=(
        (True, WalletState.PENDING, WalletUserStatus.PENDING, WalletUserType.EMPLOYEE),
        (True, WalletState.PENDING, WalletUserStatus.PENDING, WalletUserType.DEPENDENT),
        (True, WalletState.PENDING, WalletUserStatus.ACTIVE, WalletUserType.EMPLOYEE),
        (True, WalletState.PENDING, WalletUserStatus.ACTIVE, WalletUserType.DEPENDENT),
        (True, WalletState.PENDING, WalletUserStatus.DENIED, WalletUserType.EMPLOYEE),
        (True, WalletState.PENDING, WalletUserStatus.DENIED, WalletUserType.DEPENDENT),
        (
            True,
            WalletState.QUALIFIED,
            WalletUserStatus.PENDING,
            WalletUserType.EMPLOYEE,
        ),
        (
            True,
            WalletState.QUALIFIED,
            WalletUserStatus.PENDING,
            WalletUserType.DEPENDENT,
        ),
        (True, WalletState.QUALIFIED, WalletUserStatus.ACTIVE, WalletUserType.EMPLOYEE),
        (
            True,
            WalletState.QUALIFIED,
            WalletUserStatus.ACTIVE,
            WalletUserType.DEPENDENT,
        ),
        (True, WalletState.QUALIFIED, WalletUserStatus.DENIED, WalletUserType.EMPLOYEE),
        (
            True,
            WalletState.QUALIFIED,
            WalletUserStatus.DENIED,
            WalletUserType.DEPENDENT,
        ),
        (
            True,
            WalletState.DISQUALIFIED,
            WalletUserStatus.PENDING,
            WalletUserType.EMPLOYEE,
        ),
        (
            True,
            WalletState.DISQUALIFIED,
            WalletUserStatus.PENDING,
            WalletUserType.DEPENDENT,
        ),
        (
            True,
            WalletState.DISQUALIFIED,
            WalletUserStatus.ACTIVE,
            WalletUserType.EMPLOYEE,
        ),
        (
            True,
            WalletState.DISQUALIFIED,
            WalletUserStatus.ACTIVE,
            WalletUserType.DEPENDENT,
        ),
        (
            True,
            WalletState.DISQUALIFIED,
            WalletUserStatus.DENIED,
            WalletUserType.EMPLOYEE,
        ),
        (
            True,
            WalletState.DISQUALIFIED,
            WalletUserStatus.DENIED,
            WalletUserType.DEPENDENT,
        ),
        (True, WalletState.EXPIRED, WalletUserStatus.PENDING, WalletUserType.EMPLOYEE),
        (True, WalletState.EXPIRED, WalletUserStatus.PENDING, WalletUserType.DEPENDENT),
        (True, WalletState.EXPIRED, WalletUserStatus.ACTIVE, WalletUserType.EMPLOYEE),
        (True, WalletState.EXPIRED, WalletUserStatus.ACTIVE, WalletUserType.DEPENDENT),
        (True, WalletState.EXPIRED, WalletUserStatus.DENIED, WalletUserType.EMPLOYEE),
        (True, WalletState.EXPIRED, WalletUserStatus.DENIED, WalletUserType.DEPENDENT),
        (True, WalletState.RUNOUT, WalletUserStatus.PENDING, WalletUserType.EMPLOYEE),
        (True, WalletState.RUNOUT, WalletUserStatus.PENDING, WalletUserType.DEPENDENT),
        (True, WalletState.RUNOUT, WalletUserStatus.ACTIVE, WalletUserType.EMPLOYEE),
        (True, WalletState.RUNOUT, WalletUserStatus.ACTIVE, WalletUserType.DEPENDENT),
        (True, WalletState.RUNOUT, WalletUserStatus.DENIED, WalletUserType.EMPLOYEE),
        (True, WalletState.RUNOUT, WalletUserStatus.DENIED, WalletUserType.DEPENDENT),
        (False, WalletState.PENDING, WalletUserStatus.PENDING, WalletUserType.EMPLOYEE),
        (
            False,
            WalletState.PENDING,
            WalletUserStatus.PENDING,
            WalletUserType.DEPENDENT,
        ),
        (False, WalletState.PENDING, WalletUserStatus.ACTIVE, WalletUserType.EMPLOYEE),
        (False, WalletState.PENDING, WalletUserStatus.ACTIVE, WalletUserType.DEPENDENT),
        (False, WalletState.PENDING, WalletUserStatus.DENIED, WalletUserType.EMPLOYEE),
        (False, WalletState.PENDING, WalletUserStatus.DENIED, WalletUserType.DEPENDENT),
        (
            False,
            WalletState.QUALIFIED,
            WalletUserStatus.PENDING,
            WalletUserType.EMPLOYEE,
        ),
        (
            False,
            WalletState.QUALIFIED,
            WalletUserStatus.PENDING,
            WalletUserType.DEPENDENT,
        ),
        (
            False,
            WalletState.QUALIFIED,
            WalletUserStatus.ACTIVE,
            WalletUserType.EMPLOYEE,
        ),
        (
            False,
            WalletState.QUALIFIED,
            WalletUserStatus.ACTIVE,
            WalletUserType.DEPENDENT,
        ),
        (
            False,
            WalletState.QUALIFIED,
            WalletUserStatus.DENIED,
            WalletUserType.EMPLOYEE,
        ),
        (
            False,
            WalletState.QUALIFIED,
            WalletUserStatus.DENIED,
            WalletUserType.DEPENDENT,
        ),
        (
            False,
            WalletState.DISQUALIFIED,
            WalletUserStatus.PENDING,
            WalletUserType.EMPLOYEE,
        ),
        (
            False,
            WalletState.DISQUALIFIED,
            WalletUserStatus.PENDING,
            WalletUserType.DEPENDENT,
        ),
        (
            False,
            WalletState.DISQUALIFIED,
            WalletUserStatus.ACTIVE,
            WalletUserType.EMPLOYEE,
        ),
        (
            False,
            WalletState.DISQUALIFIED,
            WalletUserStatus.ACTIVE,
            WalletUserType.DEPENDENT,
        ),
        (
            False,
            WalletState.DISQUALIFIED,
            WalletUserStatus.DENIED,
            WalletUserType.EMPLOYEE,
        ),
        (
            False,
            WalletState.DISQUALIFIED,
            WalletUserStatus.DENIED,
            WalletUserType.DEPENDENT,
        ),
        (False, WalletState.EXPIRED, WalletUserStatus.PENDING, WalletUserType.EMPLOYEE),
        (
            False,
            WalletState.EXPIRED,
            WalletUserStatus.PENDING,
            WalletUserType.DEPENDENT,
        ),
        (False, WalletState.EXPIRED, WalletUserStatus.ACTIVE, WalletUserType.EMPLOYEE),
        (False, WalletState.EXPIRED, WalletUserStatus.ACTIVE, WalletUserType.DEPENDENT),
        (False, WalletState.EXPIRED, WalletUserStatus.DENIED, WalletUserType.EMPLOYEE),
        (False, WalletState.EXPIRED, WalletUserStatus.DENIED, WalletUserType.DEPENDENT),
        (False, WalletState.RUNOUT, WalletUserStatus.PENDING, WalletUserType.EMPLOYEE),
        (False, WalletState.RUNOUT, WalletUserStatus.PENDING, WalletUserType.DEPENDENT),
        (False, WalletState.RUNOUT, WalletUserStatus.ACTIVE, WalletUserType.EMPLOYEE),
        (False, WalletState.RUNOUT, WalletUserStatus.ACTIVE, WalletUserType.DEPENDENT),
        (False, WalletState.RUNOUT, WalletUserStatus.DENIED, WalletUserType.EMPLOYEE),
        (False, WalletState.RUNOUT, WalletUserStatus.DENIED, WalletUserType.DEPENDENT),
    ),
)
def test_get_wallet_user_info_existing_wallet(
    client,
    api_helpers,
    enterprise_user,
    qualified_wallet,
    allow_application: bool,
    state: WalletState,
    rwu_status: WalletUserStatus,
    wallet_user_type: WalletUserType,
):
    # Not necessarily qualified :)
    qualified_wallet.state = state
    DUMMY_ROS.id = qualified_wallet.reimbursement_organization_settings_id
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=qualified_wallet.id,
        status=rwu_status,
        type=wallet_user_type,
    )
    DUMMY_ROS.id = qualified_wallet.reimbursement_organization_settings_id
    with patch(
        "wallet.resources.wallet_user_info.get_eligible_wallet_org_settings",
    ) as eligibility_settings_mock, patch(
        "wallet.resources.wallet_user_info.can_apply_for_wallet"
    ) as can_apply_for_wallet_mock:
        can_apply_for_wallet_mock.return_value = CanApplyForWalletResult(
            allow_application, False
        )
        eligibility_settings_mock.return_value = [DUMMY_ROS]
        res = client.get(
            "/api/v1/-/reimbursement_wallet/application/user_info",
            headers=api_helpers.json_headers(enterprise_user),
        )
        eligibility_settings_mock.assert_called_once()
        eligibility_settings_mock.assert_called_with(
            enterprise_user.id,
            e9y_svc=mock.ANY,
            filter_out_existing_wallets=False,
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    if state in (WalletState.PENDING, WalletState.QUALIFIED) and rwu_status in (
        WalletUserStatus.ACTIVE,
        WalletUserStatus.PENDING,
    ):
        assert content == {
            "allow_application": False,
            # Use the first org id in the list.
            "reimbursement_organization_settings_id": str(DUMMY_ROS.id),
            "existing_wallet_id": str(qualified_wallet.id),
            "existing_wallet_state": state.value,
            "is_share_a_wallet": False,
        }
    elif state == WalletState.DISQUALIFIED:
        # Users of DISQUALIFIED wallets should always be able to reapply.
        assert content == {
            "allow_application": True,
            # Use the first org id in the list.
            "reimbursement_organization_settings_id": str(DUMMY_ROS.id),
            "existing_wallet_id": str(qualified_wallet.id),
            "existing_wallet_state": state.value,
            "is_share_a_wallet": False,
        }
    elif (
        state not in (WalletState.EXPIRED, WalletState.RUNOUT)
        and rwu_status == WalletUserStatus.DENIED
    ):
        # Allow the user to reapply if allowable.
        assert content == {
            "allow_application": allow_application,
            # Use the first org id in the list.
            "reimbursement_organization_settings_id": str(DUMMY_ROS.id),
            "existing_wallet_id": str(qualified_wallet.id),
            "existing_wallet_state": state.value,
            "is_share_a_wallet": False,
        }
    elif state in (WalletState.EXPIRED, WalletState.RUNOUT):
        assert content == {
            "allow_application": allow_application,
            # Use the first org id in the list.
            "reimbursement_organization_settings_id": str(DUMMY_ROS.id),
            "existing_wallet_id": None,
            "existing_wallet_state": None,
            "is_share_a_wallet": False,
        }
    else:
        # For Phase 1 of the Wallet Qualification Service, it should not be possible
        # for a user to be a DENIED RWU of a PENDING or QUALIFIED wallet.
        assert content == {
            "allow_application": allow_application,
            # Use the first org id in the list.
            "reimbursement_organization_settings_id": str(DUMMY_ROS.id),
            "existing_wallet_id": str(qualified_wallet.id),
            "existing_wallet_state": state.value,
            "is_share_a_wallet": False,
        }


def test_get_wallet_user_info_share_a_wallet_happy_path_not_rwu(
    client,
    api_helpers,
    enterprise_user,
    shareable_wallet_and_user,  # noqa: F811
):
    # You should only be able to proceed with a QUALIFIED, shareable wallet
    # Given
    wallet, invited_user = shareable_wallet_and_user
    WalletUserInviteFactory.create(
        email=invited_user.email,
        reimbursement_wallet_id=wallet.id,
        created_by_user_id=enterprise_user.id,
        date_of_birth_provided=invited_user.date_of_birth,
    )

    rwu = (
        ReimbursementWalletRepository()
        .get_wallet_and_rwu(wallet.id, invited_user.id)
        .rwu
    )
    assert rwu is None

    # When
    with patch(
        "wallet.resources.wallet_user_info.get_eligible_wallet_org_settings",
    ) as eligibility_settings_mock:
        res = client.get(
            "/api/v1/-/reimbursement_wallet/application/user_info",
            headers=api_helpers.json_headers(invited_user),
        )
        # Then
        eligibility_settings_mock.assert_not_called()

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {
        "allow_application": True,
        "reimbursement_organization_settings_id": str(
            wallet.reimbursement_organization_settings_id
        ),
        "existing_wallet_id": str(wallet.id),
        "existing_wallet_state": wallet.state.value,
        "is_share_a_wallet": True,
    }


@pytest.mark.parametrize(
    argnames=("rwu_status",),
    argvalues=(
        (WalletUserStatus.PENDING,),
        (WalletUserStatus.ACTIVE,),
        (WalletUserStatus.DENIED,),
    ),
)
def test_get_wallet_user_info_share_a_wallet_happy_path_existing_rwu(
    client,
    api_helpers,
    enterprise_user,
    shareable_wallet_and_user,  # noqa: F811
    rwu_status: WalletUserStatus,
):
    # You should only be able to proceed with a QUALIFIED, shareable wallet
    # Given
    wallet, invited_user = shareable_wallet_and_user
    WalletUserInviteFactory.create(
        email=invited_user.email,
        reimbursement_wallet_id=wallet.id,
        created_by_user_id=enterprise_user.id,
        date_of_birth_provided=invited_user.date_of_birth,
    )

    existing_partner_rwu = ReimbursementWalletUsersFactory.create(
        user_id=invited_user.id,
        reimbursement_wallet_id=wallet.id,
        status=rwu_status,
        type=WalletUserType.DEPENDENT,  # This shouldn't matter
    )

    rwu = (
        ReimbursementWalletRepository()
        .get_wallet_and_rwu(wallet.id, invited_user.id)
        .rwu
    )
    assert rwu == existing_partner_rwu

    # When
    with patch(
        "wallet.resources.wallet_user_info.get_eligible_wallet_org_settings",
    ) as eligibility_settings_mock:
        res = client.get(
            "/api/v1/-/reimbursement_wallet/application/user_info",
            headers=api_helpers.json_headers(invited_user),
        )
        # Then
        if rwu_status == WalletUserStatus.DENIED:
            eligibility_settings_mock.assert_not_called()
        else:
            pass

    status_code = res.status_code
    content = api_helpers.load_json(res)
    if rwu_status == WalletUserStatus.DENIED:
        assert status_code == 200
        assert content == {
            "allow_application": True,
            "reimbursement_organization_settings_id": str(
                wallet.reimbursement_organization_settings_id
            ),
            "existing_wallet_id": str(wallet.id),
            "existing_wallet_state": wallet.state.value,
            "is_share_a_wallet": True,
        }
    else:
        # At this point, we proceed to use the default eligibility checks
        # Since this account has no eligibility, the user should not be allowed to apply.
        assert status_code == 200
        assert content == {
            "allow_application": False,
            "reimbursement_organization_settings_id": "",
            "existing_wallet_id": None,
            "existing_wallet_state": None,
            "is_share_a_wallet": False,
        }


def test_get_wallet_user_info_share_a_wallet_non_shareable_wallet(
    client,
    api_helpers,
    enterprise_user,
    qualified_wallet,
):
    # Given
    invited_user = EnterpriseUserFactory.create()
    invited_user.health_profile.json["birthday"] = "2000-01-01"
    WalletUserInviteFactory.create(
        email=invited_user.email,
        reimbursement_wallet_id=qualified_wallet.id,
        created_by_user_id=enterprise_user.id,
        date_of_birth_provided=invited_user.health_profile.json["birthday"],
    )

    # When
    with patch(
        "wallet.resources.wallet_user_info.get_eligible_wallet_org_settings",
    ) as eligibility_settings_mock:
        res = client.get(
            "/api/v1/-/reimbursement_wallet/application/user_info",
            headers=api_helpers.json_headers(invited_user),
        )
        # Then
        eligibility_settings_mock.assert_called_once()

    status_code = res.status_code
    content = api_helpers.load_json(res)

    # At this point, we proceed to use the default eligibility checks
    # Since this account has no eligibility, the user should not be allowed to apply.
    assert status_code == 200
    assert content == {
        "allow_application": False,
        "reimbursement_organization_settings_id": "",
        "existing_wallet_id": None,
        "existing_wallet_state": None,
        "is_share_a_wallet": False,
    }


@pytest.mark.parametrize(
    argnames=("state",),
    argvalues=(
        (WalletState.PENDING,),
        (WalletState.DISQUALIFIED,),
        (WalletState.EXPIRED,),
        (WalletState.RUNOUT,),
    ),
)
def test_get_wallet_user_info_share_a_wallet_not_qualified(
    client,
    api_helpers,
    enterprise_user,
    shareable_wallet_and_user,  # noqa: F811
    state: WalletState,
):
    # Given
    wallet, invited_user = shareable_wallet_and_user
    wallet.state = state
    WalletUserInviteFactory.create(
        email=invited_user.email,
        reimbursement_wallet_id=wallet.id,
        created_by_user_id=enterprise_user.id,
        date_of_birth_provided=invited_user.date_of_birth,
    )

    rwu = (
        ReimbursementWalletRepository()
        .get_wallet_and_rwu(wallet.id, invited_user.id)
        .rwu
    )
    assert rwu is None

    # When
    with patch(
        "wallet.resources.wallet_user_info.get_eligible_wallet_org_settings",
    ) as eligibility_settings_mock:
        res = client.get(
            "/api/v1/-/reimbursement_wallet/application/user_info",
            headers=api_helpers.json_headers(invited_user),
        )
        # Then
        eligibility_settings_mock.assert_called_once()

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {
        "allow_application": False,
        "reimbursement_organization_settings_id": "",
        "existing_wallet_id": None,
        "existing_wallet_state": None,
        "is_share_a_wallet": False,
    }


def test_get_wallet_user_info_share_a_wallet_2_existing_rwus(
    client,
    api_helpers,
    enterprise_user,
    shareable_wallet_and_user,  # noqa: F811
):
    # Given
    wallet, invited_user = shareable_wallet_and_user
    assert wallet.is_shareable is True
    WalletUserInviteFactory.create(
        email=invited_user.email,
        reimbursement_wallet_id=wallet.id,
        created_by_user_id=enterprise_user.id,
        date_of_birth_provided=invited_user.date_of_birth,
    )
    other_user = EnterpriseUserFactory.create()
    ReimbursementWalletUsersFactory.create(
        user_id=other_user.id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.EMPLOYEE,
    )

    # When
    with patch(
        "wallet.resources.wallet_user_info.get_eligible_wallet_org_settings",
    ) as eligibility_settings_mock:
        res = client.get(
            "/api/v1/-/reimbursement_wallet/application/user_info",
            headers=api_helpers.json_headers(invited_user),
        )
        # Then
        eligibility_settings_mock.assert_called_once()

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {
        "allow_application": False,
        "reimbursement_organization_settings_id": "",
        "existing_wallet_id": None,
        "existing_wallet_state": None,
        "is_share_a_wallet": False,
    }


def test_get_wallet_user_info_share_a_wallet_user_already_member(
    client,
    api_helpers,
    enterprise_user,
    shareable_wallet_and_user,  # noqa: F811
):
    # Given
    wallet, invited_user = shareable_wallet_and_user
    assert wallet.is_shareable is True
    WalletUserInviteFactory.create(
        email=invited_user.email,
        reimbursement_wallet_id=wallet.id,
        created_by_user_id=enterprise_user.id,
        date_of_birth_provided=invited_user.date_of_birth,
    )
    ReimbursementWalletUsersFactory.create(
        user_id=invited_user.id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.EMPLOYEE,
    )

    # When
    with patch(
        "wallet.resources.wallet_user_info.get_eligible_wallet_org_settings",
    ) as eligibility_settings_mock:
        res = client.get(
            "/api/v1/-/reimbursement_wallet/application/user_info",
            headers=api_helpers.json_headers(invited_user),
        )
        # Then
        eligibility_settings_mock.assert_called_once()

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {
        "allow_application": False,
        "reimbursement_organization_settings_id": "",
        "existing_wallet_id": None,
        "existing_wallet_state": None,
        "is_share_a_wallet": False,
    }


def test_get_wallet_user_info_share_a_wallet_invitation_already_claimed(
    client,
    api_helpers,
    enterprise_user,
    shareable_wallet_and_user,  # noqa: F811
):
    # Given
    wallet, invited_user = shareable_wallet_and_user
    assert wallet.is_shareable is True
    WalletUserInviteFactory.create(
        email=invited_user.email,
        reimbursement_wallet_id=wallet.id,
        created_by_user_id=enterprise_user.id,
        date_of_birth_provided=invited_user.date_of_birth,
        claimed=True,
    )

    # When
    with patch(
        "wallet.resources.wallet_user_info.get_eligible_wallet_org_settings",
    ) as eligibility_settings_mock:
        res = client.get(
            "/api/v1/-/reimbursement_wallet/application/user_info",
            headers=api_helpers.json_headers(invited_user),
        )
        # Then
        eligibility_settings_mock.assert_called_once()

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {
        "allow_application": False,
        "reimbursement_organization_settings_id": "",
        "existing_wallet_id": None,
        "existing_wallet_state": None,
        "is_share_a_wallet": False,
    }


def test_get_wallet_user_info_share_a_wallet_invitation_expired(
    client,
    api_helpers,
    enterprise_user,
    shareable_wallet_and_user,  # noqa: F811
):
    # Given
    wallet, invited_user = shareable_wallet_and_user
    assert wallet.is_shareable is True
    WalletUserInviteFactory.create(
        email=invited_user.email,
        reimbursement_wallet_id=wallet.id,
        created_by_user_id=enterprise_user.id,
        date_of_birth_provided=invited_user.date_of_birth,
        created_at=datetime.datetime(2000, 1, 1),
    )

    # When
    with patch(
        "wallet.resources.wallet_user_info.get_eligible_wallet_org_settings",
    ) as eligibility_settings_mock:
        res = client.get(
            "/api/v1/-/reimbursement_wallet/application/user_info",
            headers=api_helpers.json_headers(invited_user),
        )
        # Then
        eligibility_settings_mock.assert_called_once()

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {
        "allow_application": False,
        "reimbursement_organization_settings_id": "",
        "existing_wallet_id": None,
        "existing_wallet_state": None,
        "is_share_a_wallet": False,
    }


def test_get_wallet_user_info_share_a_wallet_invitation_information_mismatch(
    client,
    api_helpers,
    enterprise_user,
    shareable_wallet_and_user,  # noqa: F811
):
    # Given
    wallet, invited_user = shareable_wallet_and_user
    assert wallet.is_shareable is True
    WalletUserInviteFactory.create(
        email=invited_user.email,
        reimbursement_wallet_id=wallet.id,
        created_by_user_id=enterprise_user.id,
        date_of_birth_provided="2020-12-01",
    )

    # When
    with patch(
        "wallet.resources.wallet_user_info.get_eligible_wallet_org_settings",
    ) as eligibility_settings_mock:
        res = client.get(
            "/api/v1/-/reimbursement_wallet/application/user_info",
            headers=api_helpers.json_headers(invited_user),
        )
        # Then
        eligibility_settings_mock.assert_called_once()

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {
        "allow_application": False,
        "reimbursement_organization_settings_id": "",
        "existing_wallet_id": None,
        "existing_wallet_state": None,
        "is_share_a_wallet": False,
    }
