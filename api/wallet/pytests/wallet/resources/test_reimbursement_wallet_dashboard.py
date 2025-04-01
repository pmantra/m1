import datetime
from unittest.mock import Mock, patch

import pytest

from pytests.factories import (
    ClientTrackFactory,
    EnterpriseUserFactory,
    MemberTrackFactory,
    ReimbursementWalletUsersFactory,
    ResourceFactory,
)
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
from wallet.pytests.factories import ReimbursementOrganizationSettingsFactory
from wallet.resources.reimbursement_wallet_dashboard import can_apply_for_wallet


def get_dummy_ros(
    allowed_members: AllowedMembers = AllowedMembers.MULTIPLE_DEPENDENT_ONLY,
):
    return ReimbursementOrganizationSettings(
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
        allowed_members=allowed_members,
        name="name",
    )


def test_get_reimbursement_wallet_dashboard__success(
    client, enterprise_user, api_helpers
):
    with patch(
        "wallet.resources.reimbursement_wallet_dashboard.EnterpriseVerificationService"
    ) as evs_mock, patch(
        "wallet.resources.reimbursement_wallet_dashboard.get_eligible_wallet_org_settings"
    ) as get_eligible_wallet_org_settings_mock:
        get_eligible_wallet_org_settings_mock.return_value = [get_dummy_ros()]
        evs_instance = Mock()
        evs_instance.get_other_user_ids_in_family.return_value = []
        evs_mock.return_value = evs_instance
        res = client.get(
            "/api/v1/reimbursement_wallet/dashboard",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert len(content) == 3
    assert content["show_apply_for_wallet"] is True
    assert content["show_prompt_to_ask_for_invitation"] is False
    assert content["data"] == []


def test_get_reimbursement_wallet_dashboard_unable_to_infer_ros(
    client, enterprise_user, api_helpers
):
    _ = ReimbursementOrganizationSettingsFactory(
        id=6,
        organization_id=enterprise_user.organization.id,
        benefit_faq_resource_id=ResourceFactory(id=5).id,
        survey_url="fake_url",
    )
    client_track = ClientTrackFactory.create(length_in_days=100)
    MemberTrackFactory.create(
        name="pregnancy",
        user=enterprise_user,
        active=True,
        client_track_id=client_track.id,
    )

    with patch(
        "wallet.resources.reimbursement_wallet_dashboard.EnterpriseVerificationService"
    ) as evs_mock, patch(
        "wallet.resources.reimbursement_wallet_dashboard.get_eligible_wallet_org_settings",
        return_value=[],
    ):
        evs_instance = Mock()
        evs_instance.get_other_user_ids_in_family.return_value = [12345]
        evs_mock.return_value = evs_instance
        res = client.get(
            "/api/v1/reimbursement_wallet/dashboard",
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert len(content) == 3
    assert content["show_apply_for_wallet"] is False
    assert content["show_prompt_to_ask_for_invitation"] is False


def test_get_reimbursement_wallet_dashboard_unable_to_infer_ros_because_of_eligibility_issues(
    client, enterprise_user, api_helpers
):
    ReimbursementOrganizationSettingsFactory(
        id=6,
        organization_id=enterprise_user.organization.id,
        benefit_faq_resource_id=ResourceFactory(id=5).id,
        survey_url="fake_url",
    )
    client_track = ClientTrackFactory.create(length_in_days=100)
    MemberTrackFactory.create(
        name="pregnancy",
        user=enterprise_user,
        active=True,
        client_track_id=client_track.id,
    )

    with patch(
        "wallet.resources.reimbursement_wallet_dashboard.EnterpriseVerificationService"
    ) as evs_mock, patch(
        "wallet.resources.reimbursement_wallet_dashboard.get_eligible_wallet_org_settings",
        side_effect=Exception(),
    ):
        evs_instance = Mock()
        evs_instance.get_other_user_ids_in_family.return_value = [12345]
        evs_mock.return_value = evs_instance
        res = client.get(
            "/api/v1/reimbursement_wallet/dashboard",
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert len(content) == 3
    assert content["show_apply_for_wallet"] is False
    assert content["show_prompt_to_ask_for_invitation"] is False


def test_get_reimbursement_wallet_dashboard_eligible_for_all_ros(
    client, enterprise_user, api_helpers
):
    _ = ReimbursementOrganizationSettingsFactory(
        id=7,
        organization_id=enterprise_user.organization.id,
        benefit_faq_resource_id=ResourceFactory(id=8).id,
        survey_url="fake_url",
    )

    with patch(
        "wallet.resources.reimbursement_wallet_dashboard.EnterpriseVerificationService"
    ) as evs_mock:
        evs_instance = Mock()
        evs_instance.get_other_user_ids_in_family.return_value = [123456]
        evs_instance.get_eligible_features_for_user_and_org.return_value = None
        evs_mock.return_value = evs_instance
        res = client.get(
            "/api/v1/reimbursement_wallet/dashboard",
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert len(content) == 3
    assert content["show_apply_for_wallet"] is True
    assert content["show_prompt_to_ask_for_invitation"] is False


@pytest.mark.parametrize(
    # fmt: off
    argnames=("partner_ros_allowed_members", "user_ros_id_offsets", "exp"),
    ids=(
        "1. User in diff ros from partner. Apply not allowed",
        "2. User in diff ros from partner. Apply not allowed",
        "3. User in diff ros from partner. Apply allowed",
        "4. User in diff ros from partner. Apply allowed",
        "5. User in diff ros from partner. Apply allowed",
        "6. User in diff ros from partner. Apply allowed",
        "7. User in same ros as partner. Apply not allowed",
        "8. User in same ros as partner. Apply not allowed",
        "9. User in same ros as partner. Apply allowed",
        "10. User in same ros as partner. Apply allowed",
        "11. User in same ros as partner. Apply not allowed",
        "12. User in same ros as partner. Apply not allowed",
        "13. Multi-partner: User in same ros as one partner that blocks. Apply not allowed",
        "14. Multi-partner: User is not in a shared ROS. Apply allowed",
        "15. Multi-partner: User in same ros as one partner that does not block. Apply not allowed",
    ),
    argvalues=(
        # FF turned on - apply button displayed under certain use cases.
        ([AllowedMembers.SINGLE_ANY_USER], [9], False),
        ([AllowedMembers.SHAREABLE], [9], False),
        ([AllowedMembers.MULTIPLE_DEPENDENT_ONLY], [9], True),
        ([AllowedMembers.MULTIPLE_PER_MEMBER], [9], True),
        ([AllowedMembers.SINGLE_DEPENDENT_ONLY], [9], True),
        ([AllowedMembers.SINGLE_EMPLOYEE_ONLY], [9], True),
        ([AllowedMembers.SINGLE_ANY_USER], [0], False),
        ([AllowedMembers.SHAREABLE], [0], False),
        ([AllowedMembers.MULTIPLE_DEPENDENT_ONLY], [0], True),
        ([AllowedMembers.MULTIPLE_PER_MEMBER], [0], True),
        ([AllowedMembers.SINGLE_DEPENDENT_ONLY], [0], False),
        ([AllowedMembers.SINGLE_EMPLOYEE_ONLY], [0], False),
        # FF turned on, multiple partners with wallets - apply button displayed under certain use cases.
        ([AllowedMembers.SINGLE_EMPLOYEE_ONLY, AllowedMembers.SINGLE_DEPENDENT_ONLY], [9, 0], False),
        ([AllowedMembers.SINGLE_EMPLOYEE_ONLY, AllowedMembers.SINGLE_DEPENDENT_ONLY], [9, 9], True),
        ([AllowedMembers.SINGLE_EMPLOYEE_ONLY, AllowedMembers.MULTIPLE_PER_MEMBER], [9, 0], True),
    ),
    # fmt: on
)
def test_get_reimbursement_wallet_dashboard__partner_with_wallet(
    client,
    enterprise_user,
    api_helpers,
    pending_alegeus_wallet_hra_without_rwu,
    partner_ros_allowed_members,
    user_ros_id_offsets,
    exp,
):
    other_user_ids_in_family = []
    eligible_features_for_user_and_org = {}
    for i, partner_ros_allowed_member in enumerate(partner_ros_allowed_members):
        partner = EnterpriseUserFactory.create()
        other_user_ids_in_family.append(partner.id)
        rwu = ReimbursementWalletUsersFactory.create(
            reimbursement_wallet_id=pending_alegeus_wallet_hra_without_rwu.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
            user_id=partner.id,
        )
        ros = rwu.wallet.reimbursement_organization_settings
        ros.allowed_members = partner_ros_allowed_member
        user_ros = (
            ros
            if not user_ros_id_offsets[i]
            else ReimbursementOrganizationSettingsFactory.create(
                organization_id=ros.id + user_ros_id_offsets[i],
                allowed_members=AllowedMembers.MULTIPLE_DEPENDENT_ONLY,
            )
        )
        eligible_features_for_user_and_org[user_ros.id] = user_ros
    with patch(
        "wallet.resources.reimbursement_wallet_dashboard.EnterpriseVerificationService"
    ) as evs_mock, patch(
        "wallet.resources.reimbursement_wallet_dashboard.get_eligible_wallet_org_settings",
        return_value=list(eligible_features_for_user_and_org.values()),
    ):
        evs_instance = Mock()
        evs_instance.get_other_user_ids_in_family.return_value = (
            other_user_ids_in_family
        )
        evs_instance.get_eligible_features_for_user_and_org.return_value = (
            eligible_features_for_user_and_org
        )
        evs_mock.return_value = evs_instance
        res = client.get(
            "/api/v1/reimbursement_wallet/dashboard",
            headers=api_helpers.json_headers(enterprise_user),
        )
        assert res.status_code == 200
        content = api_helpers.load_json(res)
        assert content["show_apply_for_wallet"] is exp


@pytest.mark.parametrize(
    argnames="wallet_state, wallet_user_status, exp",
    argvalues=[
        (WalletState.PENDING, WalletUserStatus.ACTIVE, False),
        (WalletState.QUALIFIED, WalletUserStatus.ACTIVE, False),
        (WalletState.DISQUALIFIED, WalletUserStatus.ACTIVE, True),
        (WalletState.PENDING, WalletUserStatus.PENDING, True),
        (WalletState.QUALIFIED, WalletUserStatus.PENDING, True),
        (WalletState.DISQUALIFIED, WalletUserStatus.PENDING, True),
    ],
    ids=[
        ". Pending wallet, Active user. Not allowed to apply.",
        ". Qualified wallet, Active user. Not allowed to apply.",
        ". Disqualified wallet, Active user. Allowed to apply.",
        ". Pending wallet, Pending user. Allowed to apply.",
        ". Qualified wallet, Pending user. Allowed to apply.",
        ". Disqualified wallet, Pending user. Allowed to apply.",
    ],
)
def test_get_reimbursement_wallet_dashboard__user_already_has_wallet(
    client,
    enterprise_user,
    api_helpers,
    pending_alegeus_wallet_hra_without_rwu,
    wallet_state,
    wallet_user_status,
    exp,
):
    pending_alegeus_wallet_hra_without_rwu.state = wallet_state
    partner = EnterpriseUserFactory.create()
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=pending_alegeus_wallet_hra_without_rwu.id,
        status=wallet_user_status,
        type=WalletUserType.DEPENDENT,
        user_id=enterprise_user.id,
    )
    with patch(
        "wallet.resources.reimbursement_wallet_dashboard.EnterpriseVerificationService"
    ) as evs_mock:
        evs_instance = Mock()
        evs_instance.get_other_user_ids_in_family.return_value = [partner.id]
        evs_mock.return_value = evs_instance
        res = client.get(
            "/api/v1/reimbursement_wallet/dashboard",
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content["show_apply_for_wallet"] is exp


@pytest.mark.parametrize(argnames="feature_flag", argvalues=(False, True))
def test_get_reimbursement_wallet_dashboard__user_has_partner_without_wallet(
    client, enterprise_user, api_helpers, feature_flag
):
    partner = EnterpriseUserFactory.create()
    with patch(
        "wallet.resources.reimbursement_wallet_dashboard.EnterpriseVerificationService"
    ) as evs_mock, patch(
        "wallet.resources.reimbursement_wallet_dashboard.get_eligible_wallet_org_settings",
        return_value=[
            ReimbursementOrganizationSettingsFactory.create(organization_id=1001)
        ],
    ):
        evs_instance = Mock()
        evs_instance.get_other_user_ids_in_family.return_value = [partner.id]
        evs_instance.get_eligible_features_for_user.return_value = [1001]
        evs_mock.return_value = evs_instance
        res = client.get(
            "/api/v1/reimbursement_wallet/dashboard",
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content["show_apply_for_wallet"] is True


@pytest.mark.parametrize(
    argnames=("wallet_state",),
    argvalues=(
        (WalletState.DISQUALIFIED,),
        (WalletState.PENDING,),
        (WalletState.QUALIFIED,),
        (WalletState.RUNOUT,),
        (WalletState.EXPIRED,),
    ),
)
def test_can_apply_for_wallet(
    enterprise_user, wallet_state, pending_alegeus_wallet_hra_without_rwu
):
    """Scenarios where your partner has a wallet, and you are on the wallet dashboard page."""
    pending_alegeus_wallet_hra_without_rwu.state = wallet_state
    partner = EnterpriseUserFactory.create()
    # The partner has a wallet
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=pending_alegeus_wallet_hra_without_rwu.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.DEPENDENT,
        user_id=partner.id,
    )
    for allowed_members in AllowedMembers:
        user_ros = ReimbursementOrganizationSettingsFactory.create(
            organization_id=1001, allowed_members=allowed_members
        )
        expected_can_apply = wallet_state not in (
            WalletState.PENDING,
            WalletState.QUALIFIED,
        )
        expected_show_prompt: bool = (
            allowed_members == AllowedMembers.SHAREABLE
        ) and not expected_can_apply
        with patch(
            "wallet.resources.reimbursement_wallet_dashboard.EnterpriseVerificationService"
        ) as evs_mock, patch(
            "wallet.resources.reimbursement_wallet_dashboard.get_eligible_wallet_org_settings",
            return_value=[user_ros],
        ):
            evs_instance = Mock()
            # You are the enterprise_user.
            evs_instance.get_other_user_ids_in_family.return_value = [partner.id]
            evs_instance.get_eligible_features_for_user.return_value = [1001]
            evs_mock.return_value = evs_instance
            apply_for_wallet_result = can_apply_for_wallet(enterprise_user)
            assert apply_for_wallet_result.can_apply_for_wallet is expected_can_apply
            assert (
                apply_for_wallet_result.show_prompt_to_ask_for_invitation
                is expected_show_prompt
            )
