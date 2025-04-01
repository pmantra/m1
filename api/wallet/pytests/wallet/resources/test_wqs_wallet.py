from __future__ import annotations

import itertools
from random import choice, randint
from typing import Optional
from unittest.mock import patch

import pytest

from pytests.factories import (
    ChannelFactory,
    EnterpriseUserFactory,
    OrganizationEmployeeDependentFactory,
)
from storage.connection import db
from utils.random_string import generate_random_string
from wallet.models.constants import (
    WALLET_QUALIFICATION_SERVICE_TAG,
    ReimbursementMethod,
    ReimbursementRequestExpenseTypes,
    TaxationStateConfig,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.organization_employee_dependent import OrganizationEmployeeDependent
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.models.wallet_user_invite import WalletUserInvite
from wallet.pytests.factories import (
    ReimbursementOrganizationSettingsFactory,
    ReimbursementOrgSettingsExpenseTypeFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
    WalletUserInviteFactory,
)
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository
from wallet.resources.reimbursement_wallet_dashboard import CanApplyForWalletResult
from wallet.resources.wqs_wallet import (
    PUT_ACCEPTABLE_WALLET_STATES,
    WQS_MONO_RESOURCE,
    WQSWalletPUTResponse,
)
from wallet.services.reimbursement_wallet_state_change import (
    WALLET_APPLICATION_MANUAL_REVIEW_TAG,
    handle_qualification_of_wallet_created_by_wqs,
)


@pytest.fixture(scope="function")
def e9y_verification(eligibility_factories, enterprise_user):
    verification = eligibility_factories.VerificationFactory.create(
        user_id=1, organization_id=enterprise_user.organization_employee.organization_id
    )
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as mock_get_verification_for_user, patch(
        "eligibility.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
        return_value={enterprise_user.organization.id},
    ):
        mock_get_verification_for_user.return_value = verification
        yield verification


@pytest.fixture(scope="function")
def e9y_member(eligibility_factories, enterprise_user):
    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1, organization_id=enterprise_user.organization_employee.organization_id
    )
    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as mock_member_id_search:
        mock_member_id_search.return_value = e9y_member
        yield e9y_member


VALID_PRIMARY_EXPENSE_TYPE_IN_TEST = ReimbursementRequestExpenseTypes.FERTILITY
TEST_EMAIL = "thepartner@partner.part"


def random_primary_expense_type() -> ReimbursementRequestExpenseTypes:
    return choice(list(ReimbursementRequestExpenseTypes))


def random_wallet_state() -> WalletState:
    return choice(list(WalletState))


def _get_post_arg_names() -> tuple[str]:
    return (
        "can_apply_for_wallet_mock_value",
        "wallet_user_status",
        "wallet_user_type",
        "state",
        "primary_expense_type",
        "is_inside_the_usa",
        "matched_reimbursement_method",
        "dependent_name",
        "is_dependent_existing",
    )


def _collect_all_post_test_cases():
    arg_name_to_values_map = {
        "can_apply_for_wallet_mock_value": (True, False),
        "wallet_user_status": (
            WalletUserStatus.ACTIVE,
        ),  # only pick part of the available wallet_user_status for testing to reduce the number of tests to run
        "wallet_user_type": (
            WalletUserType.EMPLOYEE,
            WalletUserType.DEPENDENT,
        ),  # only pick part of the available user_type for testing to reduce the number of tests to run
        "state": (
            WalletState.QUALIFIED,
            WalletState.DISQUALIFIED,
            WalletState.PENDING,
        ),  # only pick part of the available state for testing to reduce the number of tests to run
        "primary_expense_type": (
            VALID_PRIMARY_EXPENSE_TYPE_IN_TEST.value,
            None,
        ),  # only pick part of the available primary_expense_type for testing to reduce the number of tests to run
        "is_inside_the_usa": (True, False, None),
        "matched_reimbursement_method": (ReimbursementMethod.PAYROLL,),
        "dependent_name": (("foo", "bar"), (None, None)),
        "is_dependent_existing": (True, False),
    }

    return tuple(
        itertools.product(
            *(
                arg_name_to_values_map[arg]
                for arg in _get_post_arg_names()
                if arg in arg_name_to_values_map
            )
        )
    )


def share_a_wallet_put_test_cases() -> tuple[tuple]:
    wallet_user_statuses = [
        item.value
        for item in [
            WalletUserStatus.ACTIVE,
            WalletUserStatus.DENIED,
            WalletUserStatus.PENDING,
        ]
    ]
    wallet_user_types = list(item.value for item in WalletUserType)
    return tuple(itertools.product(wallet_user_statuses, wallet_user_types))


@pytest.mark.parametrize(
    argnames=_get_post_arg_names(),
    argvalues=_collect_all_post_test_cases(),
)
def test_post_user_wqs_wallet(
    client,
    enterprise_user,
    api_helpers,
    eligibility_factories,
    ff_test_data,
    can_apply_for_wallet_mock_value: bool,
    state: str,
    wallet_user_status: str,
    wallet_user_type: str,
    primary_expense_type: Optional[str],
    is_inside_the_usa: Optional[bool],
    matched_reimbursement_method: ReimbursementMethod,
    dependent_name: tuple[Optional[str]],
    is_dependent_existing: bool,
):
    organization_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=enterprise_user.organization.id
    )

    data = {
        "reimbursement_organization_settings_id": organization_settings.id,
        "state": state,
        "wallet_user_status": wallet_user_status,
        "wallet_user_type": wallet_user_type,
        "primary_expense_type": primary_expense_type,
        "is_inside_the_usa": is_inside_the_usa,
        "dependent_first_name": dependent_name[0],
        "dependent_last_name": dependent_name[1],
    }

    ReimbursementOrgSettingsExpenseTypeFactory.create(
        reimbursement_organization_settings_id=organization_settings.id,
        expense_type=VALID_PRIMARY_EXPENSE_TYPE_IN_TEST,
        taxation_status=TaxationStateConfig.SPLIT_DX_INFERTILITY,
        reimbursement_method=matched_reimbursement_method,
    )

    alegeus_dependent_id = generate_random_string(10)

    previous_reimbursement_wallet_user = db.session.query(
        ReimbursementWalletUsers
    ).one_or_none()
    # Make sure that the post is creating an RWU
    assert previous_reimbursement_wallet_user is None
    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=enterprise_user.organization.id,
        verification_2_id=1001,
    )
    e9y_member_verification.eligibility_member_id = None
    zendesk_ticket_id = randint(1, 2_000_000_000)
    existing_dependent_created = False

    with patch(
        "eligibility.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
        return_value={enterprise_user.organization.id},
    ), patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
        return_value=e9y_member_verification,
    ), patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock, patch(
        "wallet.services.reimbursement_wallet_messaging.send_general_ticket_to_zendesk"
    ) as zendesk_ticket_mock, patch(
        "wallet.resources.wqs_wallet.can_apply_for_wallet"
    ) as can_apply_for_wallet_mock, patch(
        "wallet.resources.wqs_wallet.handle_qualification_of_wallet_created_by_wqs.delay",
        side_effect=handle_qualification_of_wallet_created_by_wqs,
    ) as handle_qualification_of_wallet_created_by_wqs_mock:
        can_apply_for_wallet_mock.return_value = CanApplyForWalletResult(
            can_apply_for_wallet_mock_value, False
        )
        member_id_search_mock.return_value = e9y_member_verification
        zendesk_ticket_mock.return_value = zendesk_ticket_id
        res = client.post(
            "/api/v1/-/wqs/wallet",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(data),
        )
        assert handle_qualification_of_wallet_created_by_wqs_mock.called == (
            res.status_code != 403 and state == WalletState.QUALIFIED
        )

    if can_apply_for_wallet_mock_value is False:
        assert res.status_code == 403
    else:
        assert res.status_code == 201
        content = api_helpers.load_json(res)
        reimbursement_wallet_user = (
            db.session.query(ReimbursementWalletUsers)
            .filter(ReimbursementWalletUsers.user_id == enterprise_user.id)
            .one()
        )

        wallet_id = reimbursement_wallet_user.reimbursement_wallet_id
        expected_reimbursement_method = ReimbursementMethod.DIRECT_DEPOSIT

        if is_dependent_existing:
            dependent: Optional[OrganizationEmployeeDependent] = (
                db.session.query(OrganizationEmployeeDependent).filter(
                    OrganizationEmployeeDependent.reimbursement_wallet_id == wallet_id
                )
            ).scalar()
            if not dependent:
                existing_dependent_created = True
                if wallet_user_type == WalletUserType.EMPLOYEE:
                    if dependent_name[0] is not None and dependent_name[1] is not None:
                        OrganizationEmployeeDependentFactory.create(
                            first_name=dependent_name[0],
                            last_name=dependent_name[1],
                            alegeus_dependent_id=alegeus_dependent_id,
                            reimbursement_wallet_id=wallet_id,
                        )
                else:
                    OrganizationEmployeeDependentFactory.create(
                        first_name=enterprise_user.first_name,
                        last_name=enterprise_user.last_name,
                        alegeus_dependent_id=alegeus_dependent_id,
                        reimbursement_wallet_id=wallet_id,
                    )
        if primary_expense_type is None:
            # The default reimbursement method for creating the wallet is DIRECT_DEPOSIT
            # when reimbursement method is null in the request
            expected_reimbursement_method = ReimbursementMethod.DIRECT_DEPOSIT
        elif is_inside_the_usa is False:
            expected_reimbursement_method = ReimbursementMethod.PAYROLL
        else:
            expected_reimbursement_method = matched_reimbursement_method

        expected_content = {
            "wallet_id": str(wallet_id),
            "wallet_user_status": wallet_user_status,
            "state": state,
            "wallet_user_type": wallet_user_type,
            "reimbursement_method": str(expected_reimbursement_method)
            if expected_reimbursement_method is not None
            else None,
            "primary_expense_type": primary_expense_type,
            "is_inside_the_usa": is_inside_the_usa,
        }
        assert content == expected_content

        wallet_state = (
            db.session.query(ReimbursementWallet.state)
            .filter(ReimbursementWallet.id == wallet_id)
            .scalar()
        )

        wallet_primary_expense_type = (
            db.session.query(ReimbursementWallet.primary_expense_type)
            .filter(ReimbursementWallet.id == wallet_id)
            .scalar()
        )

        wallet_reimbursement_method = (
            db.session.query(ReimbursementWallet.reimbursement_method)
            .filter(ReimbursementWallet.id == wallet_id)
            .scalar()
        )

        wallet_note = (
            db.session.query(ReimbursementWallet.note)
            .filter(ReimbursementWallet.id == wallet_id)
            .scalar()
        )

        reimbursement_wallet = (
            db.session.query(ReimbursementWallet)
            .filter(ReimbursementWallet.id == wallet_id)
            .one()
        )

        expected_wallet_state = WalletState(state)
        assert wallet_state == expected_wallet_state
        assert reimbursement_wallet_user.status.value == wallet_user_status
        assert reimbursement_wallet_user.type.value == wallet_user_type
        assert reimbursement_wallet_user.channel_id is not None
        assert (
            reimbursement_wallet.initial_eligibility_verification_2_id
            == e9y_member_verification.verification_2_id
        )
        assert WALLET_QUALIFICATION_SERVICE_TAG in wallet_note

        if primary_expense_type is not None:
            assert (
                wallet_primary_expense_type
                == ReimbursementRequestExpenseTypes[primary_expense_type]
            )
        else:
            assert wallet_primary_expense_type is None

        assert expected_reimbursement_method == wallet_reimbursement_method

        dependent: Optional[OrganizationEmployeeDependent] = (
            db.session.query(OrganizationEmployeeDependent).filter(
                OrganizationEmployeeDependent.reimbursement_wallet_id == wallet_id
            )
        ).scalar()

        if is_dependent_existing:
            if wallet_user_type == WalletUserType.EMPLOYEE:
                if dependent_name[0] is not None and dependent_name[1] is not None:
                    assert dependent.first_name == dependent_name[0]
                    assert dependent.last_name == dependent_name[1]
                    assert dependent.reimbursement_wallet_id == wallet_id
                    if existing_dependent_created:
                        assert dependent.alegeus_dependent_id == alegeus_dependent_id
                else:
                    assert dependent is None
            else:
                assert dependent.first_name == enterprise_user.first_name
                assert dependent.last_name == enterprise_user.last_name
                assert dependent.reimbursement_wallet_id == wallet_id
                if existing_dependent_created:
                    assert dependent.alegeus_dependent_id == alegeus_dependent_id
        else:
            if wallet_user_type == WalletUserType.EMPLOYEE:
                if dependent_name[0] is not None and dependent_name[1] is not None:
                    assert dependent.first_name == dependent_name[0]
                    assert dependent.last_name == dependent_name[1]
                    assert dependent.reimbursement_wallet_id == wallet_id
                    assert (
                        dependent.alegeus_dependent_id is not None
                        and dependent.alegeus_dependent_id != alegeus_dependent_id
                    )
                else:
                    assert dependent is None
            else:
                assert dependent.first_name == enterprise_user.first_name
                assert dependent.last_name == enterprise_user.last_name
                assert dependent.reimbursement_wallet_id == wallet_id
                assert (
                    dependent.alegeus_dependent_id is not None
                    and dependent.alegeus_dependent_id != alegeus_dependent_id
                )
        # zendesk ticket checks - assert tickets were not created. (this test does not check for pending wallets)
        assert zendesk_ticket_mock.called == (state == WalletState.PENDING)
        if zendesk_ticket_mock.called:
            kwargs = zendesk_ticket_mock.call_args.kwargs
            assert WALLET_APPLICATION_MANUAL_REVIEW_TAG in kwargs["tags"]
            assert kwargs["called_by"] == WQS_MONO_RESOURCE
        else:
            assert reimbursement_wallet_user.zendesk_ticket_id is None


def test_post_user_wqs_wallet_async_qualification(
    client,
    enterprise_user,
    api_helpers,
    eligibility_factories,
    ff_test_data,
):
    organization_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=enterprise_user.organization.id
    )

    data = {
        "reimbursement_organization_settings_id": organization_settings.id,
        "state": WalletState.QUALIFIED,
        "wallet_user_status": "ACTIVE",
        "wallet_user_type": WalletUserType.EMPLOYEE.value,
        "primary_expense_type": VALID_PRIMARY_EXPENSE_TYPE_IN_TEST.value,
        "is_inside_the_usa": True,
        "dependent_first_name": "Sarah",
        "dependent_last_name": "Millican",
    }

    ReimbursementOrgSettingsExpenseTypeFactory.create(
        reimbursement_organization_settings_id=organization_settings.id,
        expense_type=VALID_PRIMARY_EXPENSE_TYPE_IN_TEST,
        taxation_status=TaxationStateConfig.SPLIT_DX_INFERTILITY,
        reimbursement_method=ReimbursementMethod.DIRECT_DEPOSIT,
    )

    previous_reimbursement_wallet_user = db.session.query(
        ReimbursementWalletUsers
    ).one_or_none()
    # Make sure that the post is creating an RWU
    assert previous_reimbursement_wallet_user is None
    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=enterprise_user.organization.id,
        verification_2_id=1001,
    )
    e9y_member_verification.eligibility_member_id = None
    zendesk_ticket_id = randint(1, 2_000_000_000)

    with patch(
        "eligibility.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
        return_value={enterprise_user.organization.id},
    ), patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
        return_value=e9y_member_verification,
    ), patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock, patch(
        "wallet.services.reimbursement_wallet_messaging.send_general_ticket_to_zendesk"
    ) as zendesk_ticket_mock, patch(
        "wallet.resources.wqs_wallet.can_apply_for_wallet"
    ) as can_apply_for_wallet_mock, patch(
        "wallet.resources.wqs_wallet.handle_qualification_of_wallet_created_by_wqs.delay",
        side_effect=handle_qualification_of_wallet_created_by_wqs,
    ):
        can_apply_for_wallet_mock.return_value = CanApplyForWalletResult(True, False)
        member_id_search_mock.return_value = e9y_member_verification
        zendesk_ticket_mock.return_value = zendesk_ticket_id
        res = client.post(
            "/api/v1/-/wqs/wallet",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(data),
        )
        assert res.status_code == 201
        content = api_helpers.load_json(res)
        reimbursement_wallet_user = (
            db.session.query(ReimbursementWalletUsers)
            .filter(ReimbursementWalletUsers.user_id == enterprise_user.id)
            .one()
        )

        wallet_id = reimbursement_wallet_user.reimbursement_wallet_id
        expected_content = {
            "wallet_id": str(wallet_id),
            "wallet_user_status": "ACTIVE",
            "state": "QUALIFIED",
            "wallet_user_type": "EMPLOYEE",
            "reimbursement_method": "DIRECT_DEPOSIT",
            "primary_expense_type": VALID_PRIMARY_EXPENSE_TYPE_IN_TEST.value,
            "is_inside_the_usa": True,
        }
        assert content == expected_content
        # this particular wallet was qualified by the async qualification process
        res_wallet = db.session.query(ReimbursementWallet).get(wallet_id)
        assert res_wallet.state == WalletState.QUALIFIED
        # zendesk was not called since the wallet was qualified.
        assert zendesk_ticket_mock.called is False


def test__post_user_wqs_wallet_dependent_alegeus_id(
    client,
    enterprise_user,
    api_helpers,
    eligibility_factories,
    ff_test_data,
):
    enterprise_user.first_name = "Test Dependent"
    enterprise_user.last_name = "Test Last Name"
    organization_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=enterprise_user.organization.id
    )
    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=enterprise_user.organization.id,
        verification_2_id=1001,
    )
    data = {
        "reimbursement_organization_settings_id": organization_settings.id,
        "state": WalletState.QUALIFIED,
        "wallet_user_status": "ACTIVE",
        "wallet_user_type": WalletUserType.DEPENDENT.value,
        "primary_expense_type": VALID_PRIMARY_EXPENSE_TYPE_IN_TEST.value,
        "is_inside_the_usa": True,
        "dependent_first_name": enterprise_user.first_name,
        "dependent_last_name": enterprise_user.last_name,
    }
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
        return_value=e9y_member_verification,
    ), patch(
        "wallet.resources.wqs_wallet.can_apply_for_wallet",
        return_value=CanApplyForWalletResult(True, False),
    ), patch(
        "wallet.resources.wqs_wallet.open_zendesk_ticket"
    ), patch(
        "wallet.resources.wqs_wallet.handle_qualification_of_wallet_created_by_wqs"
    ):
        res = client.post(
            "/api/v1/-/wqs/wallet",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(data),
        )
    assert res.status_code == 201
    wallet_id = res.json.get("wallet_id")
    oed = OrganizationEmployeeDependent.query.filter(
        OrganizationEmployeeDependent.first_name == enterprise_user.first_name,
        OrganizationEmployeeDependent.last_name == enterprise_user.last_name,
        OrganizationEmployeeDependent.reimbursement_wallet_id == wallet_id,
    ).one()
    rwu = ReimbursementWalletUsers.query.filter(
        ReimbursementWalletUsers.user_id == enterprise_user.id,
        ReimbursementWalletUsers.type == WalletUserType.DEPENDENT,
    ).one()
    assert rwu.alegeus_dependent_id == oed.alegeus_dependent_id


@pytest.mark.parametrize(
    argnames=(
        "can_apply_for_wallet_mock_value",
        "state",
        "wallet_user_status",
    ),
    argvalues=(
        (True, WalletState.PENDING, WalletUserStatus.ACTIVE),
        (True, WalletState.PENDING, WalletUserStatus.PENDING),
        (True, WalletState.PENDING, WalletUserStatus.DENIED),
        (True, WalletState.QUALIFIED, WalletUserStatus.ACTIVE),
        (True, WalletState.QUALIFIED, WalletUserStatus.PENDING),
        (True, WalletState.QUALIFIED, WalletUserStatus.DENIED),
        (True, WalletState.DISQUALIFIED, WalletUserStatus.ACTIVE),
        (True, WalletState.DISQUALIFIED, WalletUserStatus.PENDING),
        (True, WalletState.DISQUALIFIED, WalletUserStatus.DENIED),
        (True, WalletState.RUNOUT, WalletUserStatus.ACTIVE),
        (True, WalletState.RUNOUT, WalletUserStatus.PENDING),
        (True, WalletState.RUNOUT, WalletUserStatus.DENIED),
        (True, WalletState.EXPIRED, WalletUserStatus.ACTIVE),
        (True, WalletState.EXPIRED, WalletUserStatus.PENDING),
        (True, WalletState.EXPIRED, WalletUserStatus.DENIED),
        (False, WalletState.PENDING, WalletUserStatus.ACTIVE),
        (False, WalletState.PENDING, WalletUserStatus.PENDING),
        (False, WalletState.PENDING, WalletUserStatus.DENIED),
        (False, WalletState.QUALIFIED, WalletUserStatus.ACTIVE),
        (False, WalletState.QUALIFIED, WalletUserStatus.PENDING),
        (False, WalletState.QUALIFIED, WalletUserStatus.DENIED),
        (False, WalletState.DISQUALIFIED, WalletUserStatus.ACTIVE),
        (False, WalletState.DISQUALIFIED, WalletUserStatus.PENDING),
        (False, WalletState.DISQUALIFIED, WalletUserStatus.DENIED),
        (False, WalletState.RUNOUT, WalletUserStatus.ACTIVE),
        (False, WalletState.RUNOUT, WalletUserStatus.PENDING),
        (False, WalletState.RUNOUT, WalletUserStatus.DENIED),
        (False, WalletState.EXPIRED, WalletUserStatus.ACTIVE),
        (False, WalletState.EXPIRED, WalletUserStatus.PENDING),
        (False, WalletState.EXPIRED, WalletUserStatus.DENIED),
    ),
)
def test_post_wqs_wallet_errors_existing_pending_or_active_rwu(
    client,
    enterprise_user,
    api_helpers,
    eligibility_factories,
    can_apply_for_wallet_mock_value: bool,
    state: WalletState,
    wallet_user_status: WalletUserStatus,
):
    reimbursement_organization_settings = (
        ReimbursementOrganizationSettingsFactory.create(
            organization_id=enterprise_user.organization.id
        )
    )
    data = {
        "state": "PENDING",
        "reimbursement_organization_settings_id": reimbursement_organization_settings.id,
        "wallet_user_type": "EMPLOYEE",
        "wallet_user_status": "PENDING",
    }
    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1, organization_id=enterprise_user.organization.id
    )
    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1, organization_id=enterprise_user.organization.id
    )
    channel = ChannelFactory.create()
    existing_wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=reimbursement_organization_settings,
        initial_eligibility_member_id=e9y_member.id,
        state=state,
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=existing_wallet.id,
        channel_id=channel.id,
        zendesk_ticket_id=randint(1, 2_000_000_000),
        status=wallet_user_status,
    )
    with patch(
        "eligibility.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
        return_value={enterprise_user.organization.id},
    ), patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
        return_value=e9y_member_verification,
    ), patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock, patch(
        "wallet.resources.wqs_wallet.can_apply_for_wallet"
    ) as can_apply_for_wallet_mock:
        can_apply_for_wallet_mock.return_value = CanApplyForWalletResult(
            can_apply_for_wallet_mock_value, False
        )
        member_id_search_mock.return_value = e9y_member_verification
        res = client.post(
            "/api/v1/-/wqs/wallet",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(data),
        )
        content = api_helpers.load_json(res)
    if can_apply_for_wallet_mock_value is False:
        assert res.status_code == 403
    elif wallet_user_status == WalletUserStatus.DENIED:
        # We don't care if the user is already denied.
        # This should follow the happy path.
        assert res.status_code == 201
        assert "wallet_id" in content
    else:
        # It shouldn't matter what state the existing wallet is in.
        # This should never happen.
        assert res.status_code == 409


def test_put_user_wallet_fail_no_wallet(client, enterprise_user, api_helpers):
    data = {
        "state": WalletState.PENDING.value,
        "wallet_user_status": WalletUserStatus.PENDING.value,
    }
    fake_wallet_id = randint(1, 2_000_000_000)
    res = client.put(
        f"/api/v1/-/wqs/wallet/{fake_wallet_id}",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data(data),
    )
    assert res.status_code == 404


def _get_put_arg_names():
    return (
        "wallet_user_status",
        "wallet_user_type",
        "state",
        "primary_expense_type",
        "is_inside_the_usa",
        "matched_reimbursement_method",
        "dependent_name",
        "is_dependent_existing",
    )


def _collect_all_put_test_cases():
    arg_name_to_values_map = {
        "wallet_user_status": (WalletUserStatus.PENDING, WalletUserStatus.ACTIVE),
        # only pick part of the available wallet_user_status for testing to reduce the number of tests to run
        "wallet_user_type": (WalletUserType.DEPENDENT, WalletUserType.EMPLOYEE),
        # only pick part of the available user_type for testing to reduce the number of tests to run
        "state": (WalletState.QUALIFIED, WalletState.DISQUALIFIED),
        # only pick part of the available state for testing to reduce the number of tests to run
        "primary_expense_type": (
            VALID_PRIMARY_EXPENSE_TYPE_IN_TEST.value,
            None,
        ),  # only pick part of the available primary_expense_type for testing to reduce the number of tests to run
        "is_inside_the_usa": (True, False, None),
        "matched_reimbursement_method": (ReimbursementMethod.PAYROLL,),
        "dependent_name": (("foo", "bar"), (None, None)),
        "is_dependent_existing": (True, False),
    }

    return tuple(
        itertools.product(
            *(
                arg_name_to_values_map[arg]
                for arg in _get_post_arg_names()
                if arg in arg_name_to_values_map
            )
        )
    )


@pytest.mark.parametrize(
    argnames=_get_put_arg_names(),
    argvalues=_collect_all_put_test_cases(),
)
def test_put_user_wallet_happy_paths_no_share_a_wallet(
    client,
    enterprise_user,
    api_helpers,
    wallet_user_status: str,
    wallet_user_type: str,
    state: str,
    primary_expense_type: Optional[str],
    is_inside_the_usa: Optional[bool],
    matched_reimbursement_method: ReimbursementMethod,
    dependent_name: tuple[Optional[str]],
    is_dependent_existing: bool,
):
    reimbursement_organization_settings = (
        ReimbursementOrganizationSettingsFactory.create(
            organization_id=enterprise_user.organization.id
        )
    )

    ReimbursementOrgSettingsExpenseTypeFactory.create(
        reimbursement_organization_settings_id=reimbursement_organization_settings.id,
        expense_type=VALID_PRIMARY_EXPENSE_TYPE_IN_TEST,
        taxation_status=TaxationStateConfig.SPLIT_DX_INFERTILITY,
        reimbursement_method=matched_reimbursement_method,
    )

    alegeus_dependent_id = generate_random_string(10)

    different_state = WalletState.QUALIFIED
    existing_primary_expense_type = ReimbursementRequestExpenseTypes.MENOPAUSE
    existing_wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=reimbursement_organization_settings,
        state=different_state,
        primary_expense_type=existing_primary_expense_type,
    )
    if is_dependent_existing:
        if wallet_user_type == WalletUserType.EMPLOYEE:
            if dependent_name[0] is not None and dependent_name[1] is not None:
                OrganizationEmployeeDependentFactory.create(
                    first_name=dependent_name[0],
                    last_name=dependent_name[1],
                    alegeus_dependent_id=alegeus_dependent_id,
                    reimbursement_wallet_id=existing_wallet.id,
                )
        else:
            OrganizationEmployeeDependentFactory.create(
                first_name=enterprise_user.first_name,
                last_name=enterprise_user.last_name,
                alegeus_dependent_id=alegeus_dependent_id,
                reimbursement_wallet_id=existing_wallet.id,
            )

    different_status = (
        WalletUserStatus.PENDING
        if wallet_user_status == WalletUserStatus.DENIED
        else WalletUserStatus.PENDING
    )
    rwu = ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=existing_wallet.id,
        status=different_status,
        type=WalletUserType.EMPLOYEE
        if wallet_user_type == WalletUserType.DEPENDENT.value
        else WalletUserType.DEPENDENT,
    )
    data = {
        "state": state,
        "wallet_user_status": wallet_user_status,
        "wallet_user_type": wallet_user_type,
        "primary_expense_type": primary_expense_type,
        "is_inside_the_usa": is_inside_the_usa,
        "dependent_first_name": dependent_name[0],
        "dependent_last_name": dependent_name[1],
    }

    res = client.put(
        f"/api/v1/-/wqs/wallet/{existing_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data(data),
    )

    if WalletState[state] not in PUT_ACCEPTABLE_WALLET_STATES:
        assert res.status_code == 400
    else:
        assert res.status_code == 200
        content = api_helpers.load_json(res)

        expected_reimbursement_method = ReimbursementMethod.DIRECT_DEPOSIT
        if primary_expense_type is None:
            expected_reimbursement_method = None
        elif is_inside_the_usa is False:
            expected_reimbursement_method = ReimbursementMethod.PAYROLL
        else:
            expected_reimbursement_method = matched_reimbursement_method

        assert content == WQSWalletPUTResponse(
            state=state,
            wallet_id=str(existing_wallet.id),
            wallet_user_status=wallet_user_status,
            wallet_user_type=wallet_user_type,
            primary_expense_type=primary_expense_type,
            is_inside_the_usa=is_inside_the_usa,
            reimbursement_method=str(expected_reimbursement_method)
            if expected_reimbursement_method is not None
            else None,
        )

        updated_wallet_and_rwu = ReimbursementWalletRepository().get_wallet_and_rwu(
            wallet_id=rwu.reimbursement_wallet_id,
            user_id=rwu.user_id,
        )
        assert updated_wallet_and_rwu.wallet.state == state

        if primary_expense_type is not None:
            assert (
                updated_wallet_and_rwu.wallet.primary_expense_type
                == ReimbursementRequestExpenseTypes[primary_expense_type]
            )
        else:
            assert updated_wallet_and_rwu.wallet.primary_expense_type is None

        assert updated_wallet_and_rwu.rwu.status == wallet_user_status
        assert updated_wallet_and_rwu.rwu.type == wallet_user_type

        assert (
            updated_wallet_and_rwu.wallet.reimbursement_method
            == expected_reimbursement_method
        )

        dependent: Optional[OrganizationEmployeeDependent] = (
            db.session.query(OrganizationEmployeeDependent).filter(
                OrganizationEmployeeDependent.reimbursement_wallet_id
                == existing_wallet.id
            )
        ).scalar()

        if is_dependent_existing:
            if wallet_user_type == WalletUserType.EMPLOYEE:
                if dependent_name[0] is not None and dependent_name[1] is not None:
                    assert dependent.first_name == dependent_name[0]
                    assert dependent.last_name == dependent_name[1]
                    assert (
                        dependent.reimbursement_wallet_id
                        == updated_wallet_and_rwu.wallet.id
                    )
                    assert dependent.alegeus_dependent_id == alegeus_dependent_id
                else:
                    assert dependent is None
            else:
                assert dependent.first_name == enterprise_user.first_name
                assert dependent.last_name == enterprise_user.last_name
                assert (
                    dependent.reimbursement_wallet_id
                    == updated_wallet_and_rwu.wallet.id
                )
                assert dependent.alegeus_dependent_id == alegeus_dependent_id
        else:
            if wallet_user_type == WalletUserType.EMPLOYEE:
                if dependent_name[0] is not None and dependent_name[1] is not None:
                    assert dependent.first_name == dependent_name[0]
                    assert dependent.last_name == dependent_name[1]
                    assert (
                        dependent.reimbursement_wallet_id
                        == updated_wallet_and_rwu.wallet.id
                    )
                    assert (
                        dependent.alegeus_dependent_id is not None
                        and dependent.alegeus_dependent_id != alegeus_dependent_id
                    )
                else:
                    assert dependent is None
            else:
                assert dependent.first_name == enterprise_user.first_name
                assert dependent.last_name == enterprise_user.last_name
                assert (
                    dependent.reimbursement_wallet_id
                    == updated_wallet_and_rwu.wallet.id
                )
                assert (
                    dependent.alegeus_dependent_id is not None
                    and dependent.alegeus_dependent_id != alegeus_dependent_id
                )


@pytest.mark.parametrize(
    argnames=("wallet_user_status", "state", "wallet_user_type"),
    argvalues=(
        (WalletUserStatus.ACTIVE, WalletState.RUNOUT, "EMPLOYEE"),
        (WalletUserStatus.ACTIVE, WalletState.QUALIFIED, "EMPLOYEE"),
        (WalletUserStatus.ACTIVE, WalletState.EXPIRED, "EMPLOYEE"),
    ),
)
def test_put_user_wallet_do_not_allow_non_pending_or_disqualified(
    client,
    enterprise_user,
    api_helpers,
    state: WalletState,
    wallet_user_status: WalletUserStatus,
    wallet_user_type: str,
):
    reimbursement_organization_settings = (
        ReimbursementOrganizationSettingsFactory.create(
            organization_id=enterprise_user.organization.id
        )
    )
    existing_primary_expense_type = ReimbursementRequestExpenseTypes.FERTILITY
    new_primary_expense_type = ReimbursementRequestExpenseTypes.PRESERVATION
    different_state = WalletState.QUALIFIED
    existing_wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=reimbursement_organization_settings,
        state=different_state,
        primary_expense_type=existing_primary_expense_type,
    )
    different_status = (
        WalletUserStatus.PENDING
        if wallet_user_status == WalletUserStatus.DENIED
        else WalletUserStatus.PENDING
    )
    rwu = ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=existing_wallet.id,
        status=different_status,
        type=WalletUserType.EMPLOYEE
        if wallet_user_type == WalletUserType.DEPENDENT.value
        else WalletUserType.DEPENDENT,
    )
    data = {
        "state": state.value,
        "wallet_user_status": wallet_user_status.value,
        "wallet_user_type": wallet_user_type,
        "primary_expense_type": new_primary_expense_type.value,
    }
    res = client.put(
        f"/api/v1/-/wqs/wallet/{existing_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data(data),
    )
    assert res.status_code == 400
    content = api_helpers.load_json(res)
    assert content == {}

    updated_wallet_and_rwu = ReimbursementWalletRepository().get_wallet_and_rwu(
        wallet_id=rwu.reimbursement_wallet_id,
        user_id=rwu.user_id,
    )
    assert updated_wallet_and_rwu.wallet.state == existing_wallet.state
    assert (
        updated_wallet_and_rwu.wallet.primary_expense_type
        == existing_primary_expense_type
    )
    assert updated_wallet_and_rwu.rwu.status == rwu.status
    assert updated_wallet_and_rwu.rwu.type == rwu.type


@pytest.mark.parametrize(
    argnames=("wallet_user_status", "wallet_user_type"),
    argvalues=share_a_wallet_put_test_cases(),
)
def test_put_user_wallet_happy_path_share_a_wallet_new_rwu(
    client,
    enterprise_user,
    api_helpers,
    shareable_wallet,
    wallet_user_status: str,
    wallet_user_type: str,
):
    # Given
    dob = "2000-07-04"
    wallet = shareable_wallet(enterprise_user, WalletUserType.EMPLOYEE)
    expected_wallet_state = wallet.state
    expected_primary_expense_type = wallet.primary_expense_type
    expected_reimbursement_method = wallet.reimbursement_method
    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    recipient.health_profile.json["birthday"] = dob

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=dob,
        email=TEST_EMAIL,
        claimed=False,
    )

    data = {
        "state": random_wallet_state().value,
        "wallet_user_status": wallet_user_status,
        "wallet_user_type": wallet_user_type,
        "primary_expense_type": random_primary_expense_type().value,  # Shouldn't matter
        "is_inside_the_usa": choice((True, False)),  # Shouldn't matter
        "dependent_first_name": "Blah",
        "dependent_last_name": "blah",
    }
    with patch(
        "wallet.services.reimbursement_wallet_messaging.send_general_ticket_to_zendesk"
    ) as zendesk_ticket_mock:
        zendesk_ticket_mock.return_value = 2923
        res = client.put(
            f"/api/v1/-/wqs/wallet/{wallet.id}",
            headers=api_helpers.json_headers(recipient),
            data=api_helpers.json_data(data),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)

    assert content == WQSWalletPUTResponse(
        state=wallet.state.value,
        wallet_id=str(wallet.id),
        wallet_user_status=wallet_user_status,
        wallet_user_type=wallet_user_type,
        primary_expense_type=None,
        is_inside_the_usa=None,
        reimbursement_method=None,
    )

    updated_wallet_and_rwu = ReimbursementWalletRepository().get_wallet_and_rwu(
        wallet_id=wallet.id,
        user_id=recipient.id,
    )
    if wallet_user_status == WalletUserStatus.PENDING.value:
        assert updated_wallet_and_rwu.rwu.zendesk_ticket_id is not None
    else:
        assert updated_wallet_and_rwu.rwu.zendesk_ticket_id is None

    if wallet_user_type == WalletUserType.DEPENDENT.value:
        assert updated_wallet_and_rwu.rwu.alegeus_dependent_id is not None
    else:
        assert updated_wallet_and_rwu.rwu.alegeus_dependent_id is None

    assert updated_wallet_and_rwu.rwu.channel_id is not None
    assert updated_wallet_and_rwu.wallet.state == expected_wallet_state
    assert (
        updated_wallet_and_rwu.wallet.primary_expense_type
        == ReimbursementRequestExpenseTypes(expected_primary_expense_type)
    )
    assert updated_wallet_and_rwu.rwu.status == wallet_user_status
    assert updated_wallet_and_rwu.rwu.type == wallet_user_type
    assert (
        updated_wallet_and_rwu.wallet.reimbursement_method
        == expected_reimbursement_method
    )
    assert_invitation_is_un_claimed(
        str(invitation.id), wallet_user_status != WalletUserStatus.DENIED.value
    )


@pytest.mark.parametrize(
    argnames=("wallet_user_status", "wallet_user_type"),
    argvalues=share_a_wallet_put_test_cases(),
)
def test_put_user_wallet_happy_path_share_a_wallet_reapply(
    client,
    enterprise_user,
    api_helpers,
    shareable_wallet,
    wallet_user_status: str,
    wallet_user_type: str,
):
    # Given
    dob = "2000-07-04"
    wallet = shareable_wallet(enterprise_user, WalletUserType.EMPLOYEE)
    expected_wallet_state = wallet.state
    expected_primary_expense_type = wallet.primary_expense_type
    expected_reimbursement_method = wallet.reimbursement_method
    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    recipient.health_profile.json["birthday"] = dob

    existing_rwu = ReimbursementWalletUsersFactory.create(
        user_id=recipient.id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.DENIED,
        type=WalletUserType.EMPLOYEE,
    )

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=dob,
        email=TEST_EMAIL,
        claimed=False,
    )

    data = {
        "state": random_wallet_state().value,
        "wallet_user_status": wallet_user_status,
        "wallet_user_type": wallet_user_type,
        "primary_expense_type": random_primary_expense_type().value,  # Shouldn't matter
        "is_inside_the_usa": choice((True, False)),  # Shouldn't matter
        "dependent_first_name": "Blah",
        "dependent_last_name": "blah",
    }

    res = client.put(
        f"/api/v1/-/wqs/wallet/{wallet.id}",
        headers=api_helpers.json_headers(recipient),
        data=api_helpers.json_data(data),
    )

    if wallet_user_status == WalletUserStatus.REVOKED.value:
        assert res.status_code == 400
        return

    assert res.status_code == 200
    content = api_helpers.load_json(res)

    assert content == WQSWalletPUTResponse(
        state=wallet.state.value,
        wallet_id=str(wallet.id),
        wallet_user_status=wallet_user_status,
        wallet_user_type=wallet_user_type,
        primary_expense_type=None,
        is_inside_the_usa=None,
        reimbursement_method=None,
    )

    updated_wallet_and_rwu = ReimbursementWalletRepository().get_wallet_and_rwu(
        wallet_id=wallet.id,
        user_id=recipient.id,
    )
    rwu = updated_wallet_and_rwu.rwu
    assert rwu.id == existing_rwu.id
    assert updated_wallet_and_rwu.wallet.state == expected_wallet_state
    assert (
        updated_wallet_and_rwu.wallet.primary_expense_type
        == ReimbursementRequestExpenseTypes(expected_primary_expense_type)
    )
    assert updated_wallet_and_rwu.rwu.status == wallet_user_status
    assert updated_wallet_and_rwu.rwu.type == wallet_user_type
    assert (
        updated_wallet_and_rwu.wallet.reimbursement_method
        == expected_reimbursement_method
    )
    assert_invitation_is_un_claimed(
        str(invitation.id), wallet_user_status != WalletUserStatus.DENIED.value
    )


def assert_invitation_is_un_claimed(invitation_id: str, is_claimed: bool) -> None:
    invitation = (
        db.session.query(WalletUserInvite)
        .filter(
            WalletUserInvite.id == invitation_id,
        )
        .one()
    )
    assert invitation
    assert invitation.claimed is is_claimed
