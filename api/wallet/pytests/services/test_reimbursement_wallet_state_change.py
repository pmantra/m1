from __future__ import annotations

from unittest.mock import patch

import pytest

from eligibility.pytests import factories as e9y_factories
from messaging.models.messaging import Channel
from messaging.services.zendesk import MessagingZendeskTicket
from storage.connection import db
from wallet.constants import (
    HISTORICAL_SPEND_LABEL,
    HISTORICAL_WALLET_FEATURE_FLAG,
    NUM_CREDITS_PER_CYCLE,
)
from wallet.models.constants import (
    WALLET_QUALIFICATION_SERVICE_TAG,
    BenefitTypes,
    ReimbursementRequestExpenseTypes,
    WalletState,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.models.reimbursement_wallet_credit_transaction import (
    ReimbursementCycleMemberCreditTransaction,
)
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    ReimbursementOrganizationSettingsFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.services.reimbursement_wallet_messaging import (
    get_or_create_rwu_channel,
    open_zendesk_ticket,
)
from wallet.services.reimbursement_wallet_state_change import (
    WALLET_APPLICATION_MANUAL_REVIEW_TAG,
    WQS_MONO_RQ_JOB,
    add_cycles_to_qualified_wallet,
    handle_qualification_of_wallet_created_by_wqs,
    handle_wallet_state_change,
)
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory

FLASH_MESSAGE = FlashMessage(message="Error", category=FlashMessageCategory.ERROR)


@pytest.fixture()
def mock_historical_spend_enabled(ff_test_data):
    def _mock(is_on: bool = True):
        ff_test_data.update(
            ff_test_data.flag(HISTORICAL_WALLET_FEATURE_FLAG).variation_for_all(is_on)
        )

    return _mock


@pytest.fixture()
def wallet_via_post(
    enterprise_user,
    client,
    api_helpers,
    eligibility_factories,
    wallet_state=WalletState.PENDING,
):
    organization_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=enterprise_user.organization.id
    )
    data = {"reimbursement_organization_settings_id": organization_settings.id}
    # new wallets are always created in PENDING state
    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1,
        organization_id=organization_settings.id,
    )
    enterprise_user.organization_employee.json = {"employee_start_date": "2024-01-01"}

    verification = e9y_factories.build_verification_from_oe(
        enterprise_user.id, enterprise_user.organization_employee
    )
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), patch("eligibility.e9y.grpc_service.member_id_search") as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member
        res = client.post(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(data),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"]
    # update the wallet via admin ReimbursementWalletView if the desired state is not pending
    if wallet_state is not WalletState.PENDING:
        wallet["state"] = wallet_state
    return wallet


@pytest.fixture()
def qualified_zendesk_wallet(enterprise_user):
    """
    Creates a qualified wallet attached to the enterprise_user.
    """
    enterprise_user.organization_employee.json = {"wallet_enabled": True}
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user, state=WalletState.QUALIFIED
    )
    reimbursement_wallet_user = ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
    )
    # patch calls to alegeus api,
    # get_or_create_rwu_channel, handle_state_change and open_zendesk_ticket
    # are called from admin when the wallet state is updated
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_wallet_in_alegeus"
    ) as mock_configure_wallet_in_alegeus:
        mock_configure_wallet_in_alegeus.return_value = (True, [])
        handle_wallet_state_change(wallet, WalletState.PENDING)
        get_or_create_rwu_channel(reimbursement_wallet_user)
        open_zendesk_ticket(reimbursement_wallet_user)
        return wallet


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_create_pending_wallet(
    client,
    api_helpers,
    wallet_via_post,
    db,
    enterprise_user,
):
    wallet = ReimbursementWallet.query.get(wallet_via_post["id"])

    res = client.get(
        "/api/v1/channels", headers=api_helpers.json_headers(enterprise_user)
    )
    assert res.status_code == 200
    channel_content = api_helpers.load_json(res)
    message = channel_content["data"][0]
    # PENDING wallets do not receive a welcome message
    assert message["total_messages"] == 0
    assert message["wallet_id"] == wallet_via_post["id"]
    # TODO: BEX-147 - change the zendesk_ticket_id
    assert wallet_via_post["zendesk_ticket_id"] == 0
    db.session.refresh(wallet)
    assert wallet.reimbursement_wallet_benefit is None


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_create_qualified_wallet(
    client,
    api_helpers,
    mock_zendesk,
    qualified_zendesk_wallet,
    db,
    enterprise_user,
):
    res = client.get(
        "/api/v1/channels",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200
    channel_content = api_helpers.load_json(res)
    message = channel_content["data"][0]
    # Removed automated Wallet message post-qualification
    # https://app.shortcut.com/maven-clinic/story/134997/remove-automated-wallet-message-post-qualification
    assert message["total_messages"] == 0
    assert message["wallet_id"] == str(qualified_zendesk_wallet.id)
    db.session.refresh(qualified_zendesk_wallet)
    reimbursement_wallet_user = (
        db.session.query(ReimbursementWalletUsers)
        .filter(
            ReimbursementWalletUsers.reimbursement_wallet_id
            == qualified_zendesk_wallet.id
        )
        .one()
    )
    assert reimbursement_wallet_user.zendesk_ticket_id == 0
    assert qualified_zendesk_wallet.reimbursement_wallet_benefit
    assert len(qualified_zendesk_wallet.alegeus_id) == 30


def test_send_message_to_wallet_channel(
    client, api_helpers, qualified_zendesk_wallet, mock_zendesk
):
    channel = get_affiliated_channel(qualified_zendesk_wallet.id)
    with patch("messaging.resources.messaging.send_to_zendesk.delay") as zd_task:
        data = {"body": "Test Message"}
        res = client.post(
            f"/api/v1/channel/{channel.id}/messages",
            headers=api_helpers.json_headers(qualified_zendesk_wallet.employee_member),
            data=api_helpers.json_data(data),
        )
        assert res.status_code == 201
        assert zd_task.call_count == 1


def test_zendesk_conditionals(factories, qualified_zendesk_wallet, mock_zendesk):
    channel = get_affiliated_channel(qualified_zendesk_wallet.id)
    ticket = MessagingZendeskTicket(
        message=factories.MessageFactory(
            user=qualified_zendesk_wallet.employee_member,
            channel=channel,
            body="Maven Wallet Message",
        ),
        initial_cx_message=False,
    )
    reimbursement_wallet_user = db.session.query(ReimbursementWalletUsers).one()
    assert (
        reimbursement_wallet_user.reimbursement_wallet_id == qualified_zendesk_wallet.id
    )
    assert reimbursement_wallet_user.channel_id == ticket.channel.id

    ticket.update_zendesk()

    # Check that only the user's zendesk_ticket_id was updated
    reimbursement_wallet_user = (
        db.session.query(ReimbursementWalletUsers)
        .filter(
            ReimbursementWalletUsers.reimbursement_wallet_id
            == qualified_zendesk_wallet.id
        )
        .one()
    )
    assert reimbursement_wallet_user.channel_id == ticket.channel.id
    assert reimbursement_wallet_user.zendesk_ticket_id == ticket.recorded_ticket_id
    assert "maven_wallet" in ticket.desired_ticket_tags


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_reimbursement_wallet_state_change__no_change(pending_alegeus_wallet_hra):
    old_state = WalletState.PENDING

    with patch(
        "wallet.services.reimbursement_wallet_state_change.configure_wallet_in_alegeus"
    ) as mock_configure_wallet_in_alegeus, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event:
        handle_wallet_state_change(pending_alegeus_wallet_hra, old_state)

        assert mock_configure_wallet_in_alegeus.call_count == 0
        assert mock_send_event.call_count == 0


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_reimbursement_wallet_state_change__qualified(
    pending_alegeus_wallet_hra, mock_historical_spend_enabled
):
    mock_historical_spend_enabled(False)
    old_state = pending_alegeus_wallet_hra.state
    pending_alegeus_wallet_hra.state = WalletState.QUALIFIED

    with patch(
        "wallet.services.reimbursement_wallet_state_change.assign_benefit_id"
    ) as mock_assign_benefit_id, patch(
        "wallet.services.reimbursement_wallet_state_change.assign_payments_customer_id_to_wallet"
    ) as mock_assign_payments_customer_id_to_wallet, patch(
        "wallet.services.reimbursement_wallet_state_change.configure_wallet_in_alegeus"
    ) as mock_configure_wallet_in_alegeus, patch(
        "wallet.services.reimbursement_wallet_state_change.add_cycles_to_qualified_wallet"
    ) as mock_add_cycles_to_qualified_wallet, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event:
        mock_configure_wallet_in_alegeus.return_value = (True, [])

        handle_wallet_state_change(pending_alegeus_wallet_hra, old_state)

        assert mock_assign_benefit_id.call_count == 1
        assert (
            mock_assign_payments_customer_id_to_wallet.call_count == 0
        )  # not direct payments
        assert mock_configure_wallet_in_alegeus.call_count == 1
        assert mock_add_cycles_to_qualified_wallet.call_count == 1

        assert mock_send_event.call_count == 1
        assert (
            mock_send_event.call_args.kwargs["event_name"] == "wallet_state_qualified"
        )


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_reimbursement_wallet_state_change__qualified_historic_spend_flag(
    pending_alegeus_wallet_hra,
    mock_historical_spend_enabled,
    enterprise_user,
    eligibility_factories,
    mock_ledger_entry,
):
    mock_historical_spend_enabled(True)
    old_state = pending_alegeus_wallet_hra.state
    pending_alegeus_wallet_hra.state = WalletState.QUALIFIED
    oe = enterprise_user.organization_employee
    verification = e9y_factories.build_verification_from_oe(enterprise_user.id, oe)
    mock_ledger_entry.first_name = oe.first_name
    mock_ledger_entry.last_name = oe.last_name
    mock_ledger_entry.date_of_birth = oe.date_of_birth.isoformat()

    category_associations = (
        pending_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=category_associations[
            0
        ].reimbursement_request_category,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )
    with patch(
        "wallet.services.reimbursement_wallet_state_change.assign_benefit_id"
    ) as mock_assign_benefit_id, patch(
        "wallet.services.reimbursement_wallet_state_change.assign_payments_customer_id_to_wallet"
    ) as mock_assign_payments_customer_id_to_wallet, patch(
        "wallet.services.reimbursement_wallet_state_change.configure_wallet_in_alegeus"
    ) as mock_configure_wallet_in_alegeus, patch(
        "wallet.services.reimbursement_wallet_state_change.add_cycles_to_qualified_wallet"
    ) as mock_add_cycles_to_qualified_wallet, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event, patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as mock_verification, patch(
        "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
    ) as mock_get_historic_spend_records, patch(
        "wallet.services.wallet_historical_spend.gcp_pubsub"
    ) as mock_gcp_pubsub, patch(
        "wallet.services.wallet_historical_spend.WalletHistoricalSpendService.submit_claim_to_alegeus"
    ) as mock_claim:
        mock_get_historic_spend_records.return_value = [mock_ledger_entry]
        mock_verification.return_value = verification

        mock_claim.return_value = True

        mock_configure_wallet_in_alegeus.return_value = (True, [])

        messages = handle_wallet_state_change(pending_alegeus_wallet_hra, old_state)

        historic_rr = ReimbursementRequest.query.filter(
            ReimbursementRequest.wallet == pending_alegeus_wallet_hra
        ).all()
        assert historic_rr[0].label == HISTORICAL_SPEND_LABEL
        assert historic_rr[0].amount == mock_ledger_entry.historical_spend

        assert mock_assign_benefit_id.call_count == 1
        assert (
            mock_assign_payments_customer_id_to_wallet.call_count == 0
        )  # not direct payments
        assert mock_configure_wallet_in_alegeus.call_count == 1
        assert mock_add_cycles_to_qualified_wallet.call_count == 1

        assert mock_send_event.call_count == 1
        assert (
            mock_send_event.call_args.kwargs["event_name"] == "wallet_state_qualified"
        )
        assert mock_claim.call_count == 1
        assert mock_gcp_pubsub.publish.call_count == 1
        assert len(messages) == 0


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_reimbursement_wallet_state_change_multiple_entries_with_existing_adjustments__qualified_historic_spend_flag(
    pending_alegeus_wallet_hra,
    mock_historical_spend_enabled,
    enterprise_user,
    eligibility_factories,
    mock_ledger_entry,
    mock_ledger_entry_adoption,
    valid_alegeus_plan_hra,
):
    mock_historical_spend_enabled(True)
    old_state = pending_alegeus_wallet_hra.state
    pending_alegeus_wallet_hra.state = WalletState.QUALIFIED
    oe = enterprise_user.organization_employee
    verification = e9y_factories.build_verification_from_oe(enterprise_user.id, oe)

    # Two fertility entries and one is adjusted
    fertility_entry_mock_one = mock_ledger_entry
    fertility_entry_mock_one.first_name = oe.first_name
    fertility_entry_mock_one.last_name = oe.last_name
    fertility_entry_mock_one.date_of_birth = oe.date_of_birth.isoformat()

    fertility_entry_mock_two = mock_ledger_entry
    fertility_entry_mock_two.first_name = oe.first_name
    fertility_entry_mock_two.last_name = oe.last_name
    fertility_entry_mock_two.date_of_birth = oe.date_of_birth.isoformat()
    fertility_entry_mock_two.adjustment_id = "abc2344"

    # One adoption entry without adjustments
    mock_ledger_entry_adoption.first_name = oe.first_name
    mock_ledger_entry_adoption.last_name = oe.last_name
    mock_ledger_entry_adoption.date_of_birth = oe.date_of_birth.isoformat()

    category_one = pending_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    category_two = pending_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
        1
    ].reimbursement_request_category

    category_two.label = "adoption"

    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=category_one,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=category_two,
        expense_type=ReimbursementRequestExpenseTypes.ADOPTION,
    )
    with patch(
        "wallet.services.reimbursement_wallet_state_change.assign_benefit_id"
    ), patch(
        "wallet.services.reimbursement_wallet_state_change.assign_payments_customer_id_to_wallet"
    ), patch(
        "wallet.services.reimbursement_wallet_state_change.configure_wallet_in_alegeus"
    ) as mock_configure_wallet_in_alegeus, patch(
        "wallet.services.reimbursement_wallet_state_change.add_cycles_to_qualified_wallet"
    ) as mock_add_cycles_to_qualified_wallet, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event, patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as mock_verification, patch(
        "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
    ) as mock_get_historic_spend_records, patch(
        "wallet.services.wallet_historical_spend.gcp_pubsub"
    ) as mock_gcp_pubsub, patch(
        "wallet.services.wallet_historical_spend.WalletHistoricalSpendService.submit_claim_to_alegeus"
    ) as mock_claim:
        mock_get_historic_spend_records.return_value = [
            fertility_entry_mock_one,
            fertility_entry_mock_two,
            mock_ledger_entry_adoption,
        ]
        mock_verification.return_value = verification

        mock_claim.return_value = True
        mock_configure_wallet_in_alegeus.return_value = (True, [])

        messages = handle_wallet_state_change(pending_alegeus_wallet_hra, old_state)

        historic_rrs = ReimbursementRequest.query.filter(
            ReimbursementRequest.wallet == pending_alegeus_wallet_hra
        ).all()

        assert len(historic_rrs) == 1
        assert historic_rrs[0].label == HISTORICAL_SPEND_LABEL
        assert historic_rrs[0].amount == mock_ledger_entry_adoption.historical_spend

        assert mock_configure_wallet_in_alegeus.call_count == 1
        assert mock_add_cycles_to_qualified_wallet.call_count == 1

        assert mock_send_event.call_count == 1
        assert (
            mock_send_event.call_args.kwargs["event_name"] == "wallet_state_qualified"
        )
        assert mock_claim.call_count == 1
        assert mock_gcp_pubsub.publish.call_count == 1
        assert len(messages) == 0


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_reimbursement_wallet_state_change_multiple_entries_no_adjustments__qualified_historic_spend_flag(
    pending_alegeus_wallet_hra,
    mock_historical_spend_enabled,
    enterprise_user,
    eligibility_factories,
    mock_ledger_entry,
    mock_ledger_entry_adoption,
    valid_alegeus_plan_hra,
):
    mock_historical_spend_enabled(True)
    old_state = pending_alegeus_wallet_hra.state
    pending_alegeus_wallet_hra.state = WalletState.QUALIFIED
    oe = enterprise_user.organization_employee
    verification = e9y_factories.build_verification_from_oe(enterprise_user.id, oe)

    # Two fertility entries
    fertility_entry_mock_one = mock_ledger_entry
    fertility_entry_mock_one.first_name = oe.first_name
    fertility_entry_mock_one.last_name = oe.last_name
    fertility_entry_mock_one.date_of_birth = oe.date_of_birth.isoformat()

    fertility_entry_mock_two = mock_ledger_entry
    fertility_entry_mock_two.first_name = oe.first_name
    fertility_entry_mock_two.last_name = oe.last_name
    fertility_entry_mock_two.date_of_birth = oe.date_of_birth.isoformat()

    # One adoption entry without adjustments
    mock_ledger_entry_adoption.first_name = oe.first_name
    mock_ledger_entry_adoption.last_name = oe.last_name
    mock_ledger_entry_adoption.date_of_birth = oe.date_of_birth.isoformat()

    category_one = pending_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    category_two = pending_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
        1
    ].reimbursement_request_category

    category_two.label = "adoption"

    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=category_one,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=category_two,
        expense_type=ReimbursementRequestExpenseTypes.ADOPTION,
    )
    with patch(
        "wallet.services.reimbursement_wallet_state_change.assign_benefit_id"
    ), patch(
        "wallet.services.reimbursement_wallet_state_change.assign_payments_customer_id_to_wallet"
    ), patch(
        "wallet.services.reimbursement_wallet_state_change.configure_wallet_in_alegeus"
    ) as mock_configure_wallet_in_alegeus, patch(
        "wallet.services.reimbursement_wallet_state_change.add_cycles_to_qualified_wallet"
    ) as mock_add_cycles_to_qualified_wallet, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event, patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as mock_verification, patch(
        "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
    ) as mock_get_historic_spend_records, patch(
        "wallet.services.wallet_historical_spend.gcp_pubsub"
    ) as mock_gcp_pubsub, patch(
        "wallet.services.wallet_historical_spend.WalletHistoricalSpendService.submit_claim_to_alegeus"
    ) as mock_claim:
        mock_get_historic_spend_records.return_value = [
            fertility_entry_mock_one,
            fertility_entry_mock_two,
            mock_ledger_entry_adoption,
        ]
        mock_verification.return_value = verification

        mock_claim.return_value = True
        mock_configure_wallet_in_alegeus.return_value = (True, [])

        messages = handle_wallet_state_change(pending_alegeus_wallet_hra, old_state)

        historic_rrs = ReimbursementRequest.query.filter(
            ReimbursementRequest.wallet == pending_alegeus_wallet_hra
        ).all()

        assert len(historic_rrs) == 2
        assert historic_rrs[0].label == HISTORICAL_SPEND_LABEL

        assert mock_configure_wallet_in_alegeus.call_count == 1
        assert mock_add_cycles_to_qualified_wallet.call_count == 1

        assert mock_send_event.call_count == 1
        assert (
            mock_send_event.call_args.kwargs["event_name"] == "wallet_state_qualified"
        )
        assert mock_claim.call_count == 2
        assert mock_gcp_pubsub.publish.call_count == 3
        assert len(messages) == 0


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_reimbursement_wallet_state_change__exception_historic_spend_flag(
    pending_alegeus_wallet_hra,
    mock_historical_spend_enabled,
    enterprise_user,
    eligibility_factories,
    mock_ledger_entry,
):
    mock_historical_spend_enabled(True)
    old_state = pending_alegeus_wallet_hra.state
    pending_alegeus_wallet_hra.state = WalletState.QUALIFIED
    oe = enterprise_user.organization_employee
    verification = e9y_factories.build_verification_from_oe(enterprise_user.id, oe)
    mock_ledger_entry.first_name = oe.first_name
    mock_ledger_entry.last_name = oe.last_name
    mock_ledger_entry.date_of_birth = oe.date_of_birth.isoformat()

    category_associations = (
        pending_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=category_associations[
            0
        ].reimbursement_request_category,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )
    with patch(
        "wallet.services.reimbursement_wallet_state_change.assign_benefit_id"
    ) as mock_assign_benefit_id, patch(
        "wallet.services.reimbursement_wallet_state_change.assign_payments_customer_id_to_wallet"
    ) as mock_assign_payments_customer_id_to_wallet, patch(
        "wallet.services.reimbursement_wallet_state_change.configure_wallet_in_alegeus"
    ) as mock_configure_wallet_in_alegeus, patch(
        "wallet.services.reimbursement_wallet_state_change.add_cycles_to_qualified_wallet"
    ) as mock_add_cycles_to_qualified_wallet, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event, patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as mock_verification, patch(
        "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
    ) as mock_get_historic_spend_records, patch(
        "wallet.services.wallet_historical_spend.WalletHistoricalSpendService.submit_claim_to_alegeus"
    ) as mock_claim:
        mock_get_historic_spend_records.side_effect = Exception
        mock_verification.return_value = verification

        mock_claim.return_value = True

        mock_configure_wallet_in_alegeus.return_value = (True, [])

        messages = handle_wallet_state_change(pending_alegeus_wallet_hra, old_state)

        assert mock_assign_benefit_id.call_count == 1
        assert (
            mock_assign_payments_customer_id_to_wallet.call_count == 0
        )  # not direct payments
        assert mock_configure_wallet_in_alegeus.call_count == 1
        assert mock_add_cycles_to_qualified_wallet.call_count == 1

        assert mock_send_event.call_count == 0

        assert pending_alegeus_wallet_hra.state == old_state
        assert len(messages) == 1


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_reimbursement_wallet_state_change__exception(
    pending_alegeus_wallet_hra, mock_historical_spend_enabled
):
    mock_historical_spend_enabled(False)
    old_state = pending_alegeus_wallet_hra.state
    pending_alegeus_wallet_hra.state = WalletState.QUALIFIED

    with patch(
        "wallet.services.reimbursement_wallet_state_change.assign_benefit_id"
    ) as mock_assign_benefit_id, patch(
        "wallet.services.reimbursement_wallet_state_change.assign_payments_customer_id_to_wallet"
    ) as mock_assign_payments_customer_id_to_wallet, patch(
        "wallet.services.reimbursement_wallet_state_change.configure_wallet_in_alegeus"
    ) as mock_configure_wallet_in_alegeus, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event:
        mock_configure_wallet_in_alegeus.side_effect = (
            AssertionError("exception raised."),
            None,
        )

        messages = handle_wallet_state_change(pending_alegeus_wallet_hra, old_state)

        assert mock_assign_benefit_id.call_count == 1
        assert mock_assign_payments_customer_id_to_wallet.call_count == 0
        assert mock_configure_wallet_in_alegeus.call_count == 1
        assert mock_send_event.call_count == 0

        assert pending_alegeus_wallet_hra.state == old_state
        assert len(messages) == 1


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_reimbursement_wallet_state_change__disqualified(pending_alegeus_wallet_hra):
    old_state = pending_alegeus_wallet_hra.state
    pending_alegeus_wallet_hra.state = WalletState.DISQUALIFIED

    with patch(
        "wallet.services.reimbursement_wallet_state_change.configure_wallet_in_alegeus"
    ) as mock_configure_wallet_in_alegeus, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event:
        handle_wallet_state_change(pending_alegeus_wallet_hra, old_state)

        assert mock_configure_wallet_in_alegeus.call_count == 0

        assert mock_send_event.call_count == 1
        assert (
            mock_send_event.call_args.kwargs["event_name"]
            == "wallet_state_disqualified"
        )


def test_reimbursement_wallet_state_change__adds_credits_to_cycle_based(
    qualified_alegeus_wallet_hra_cycle_based_categories, mock_historical_spend_enabled
):
    mock_historical_spend_enabled(False)
    old_state = WalletState.PENDING
    wallet_id: int = qualified_alegeus_wallet_hra_cycle_based_categories.id

    already_has_credits: bool = (
        db.session.query(ReimbursementCycleCredits)
        .filter(ReimbursementOrgSettingCategoryAssociation.id == wallet_id)
        .one_or_none()
    ) is not None

    # We also want to make sure that currency-based categories are excluded from the cycle-based
    # wallet credits population
    wallet_reimbursement_organization_settings_id: int = (
        qualified_alegeus_wallet_hra_cycle_based_categories.reimbursement_organization_settings_id
    )
    all_org_setting_category_associations: list[
        ReimbursementOrgSettingCategoryAssociation
    ] = (
        db.session.query(ReimbursementOrgSettingCategoryAssociation)
        .filter(
            ReimbursementOrgSettingCategoryAssociation.reimbursement_organization_settings_id
            == wallet_reimbursement_organization_settings_id,
        )
        .all()
    )
    num_currency_associations: int = sum(
        1 if category.benefit_type == BenefitTypes.CURRENCY else 0
        for category in all_org_setting_category_associations
    )
    # There should be at least once currency category
    assert num_currency_associations >= 1

    # This assertion also means that it has no transactions since reimbursement_cycle_member_credit_transactions
    # has a non-null foreign key requirement back to the reimbursement_cycle_credits entries
    assert already_has_credits is False

    handle_wallet_state_change(
        qualified_alegeus_wallet_hra_cycle_based_categories, old_state
    )

    # Now check the cycle-based credits balances
    credits_list: list[ReimbursementCycleCredits] = (
        db.session.query(ReimbursementCycleCredits)
        .filter(ReimbursementCycleCredits.reimbursement_wallet_id == wallet_id)
        .all()
    )

    assert credits_list
    credits_list.sort(key=lambda balance: balance.amount)
    assert len(credits_list) == 2
    assert credits_list[0].amount == 2 * NUM_CREDITS_PER_CYCLE
    assert credits_list[1].amount == 3 * NUM_CREDITS_PER_CYCLE

    # Now make sure the transactions were written
    credit_ids: list[int] = [credit.id for credit in credits_list]
    transactions: list[ReimbursementCycleMemberCreditTransaction] = (
        db.session.query(ReimbursementCycleMemberCreditTransaction)
        .filter(
            ReimbursementCycleMemberCreditTransaction.reimbursement_cycle_credits_id.in_(
                credit_ids
            )
        )
        .all()
    )

    assert transactions
    transactions.sort(key=lambda txn: txn.amount)
    assert len(transactions) == 2
    assert transactions[0].amount == 2 * NUM_CREDITS_PER_CYCLE
    assert transactions[1].amount == 3 * NUM_CREDITS_PER_CYCLE
    for transaction in transactions:
        assert (
            transaction.notes
            == f"Added {transaction.amount} credits for wallet qualification"
        )
        assert transaction.reimbursement_wallet_global_procedures_id is None
        assert transaction.reimbursement_request_id is None


def test_add_cycles_to_qualified_wallet__is_idempotent(
    qualified_alegeus_wallet_hra_cycle_based_categories, mock_historical_spend_enabled
):
    mock_historical_spend_enabled(False)
    handle_wallet_state_change(
        qualified_alegeus_wallet_hra_cycle_based_categories, WalletState.PENDING
    )
    add_cycles_to_qualified_wallet(qualified_alegeus_wallet_hra_cycle_based_categories)
    add_cycles_to_qualified_wallet(qualified_alegeus_wallet_hra_cycle_based_categories)

    # Now check the cycle-based credits balances
    credits_list: list[ReimbursementCycleCredits] = (
        db.session.query(ReimbursementCycleCredits)
        .filter(
            ReimbursementCycleCredits.reimbursement_wallet_id
            == qualified_alegeus_wallet_hra_cycle_based_categories.id
        )
        .all()
    )

    assert credits_list
    credits_list.sort(key=lambda balance: balance.amount)
    assert len(credits_list) == 2
    assert credits_list[0].amount == 2 * NUM_CREDITS_PER_CYCLE
    assert credits_list[1].amount == 3 * NUM_CREDITS_PER_CYCLE

    # Now make sure the transactions were written
    credit_ids: list[int] = [credit.id for credit in credits_list]
    transactions: list[ReimbursementCycleMemberCreditTransaction] = (
        db.session.query(ReimbursementCycleMemberCreditTransaction)
        .filter(
            ReimbursementCycleMemberCreditTransaction.reimbursement_cycle_credits_id.in_(
                credit_ids
            )
        )
        .all()
    )

    assert transactions
    transactions.sort(key=lambda txn: txn.amount)
    assert len(transactions) == 2
    assert transactions[0].amount == 2 * NUM_CREDITS_PER_CYCLE
    assert transactions[1].amount == 3 * NUM_CREDITS_PER_CYCLE
    for transaction in transactions:
        assert (
            transaction.notes
            == f"Added {transaction.amount} credits for wallet qualification"
        )
        assert transaction.reimbursement_wallet_global_procedures_id is None
        assert transaction.reimbursement_request_id is None


def test_add_cycles_to_qualified_wallet__no_credit_categories(
    enterprise_user, mock_historical_spend_enabled
):
    mock_historical_spend_enabled(False)
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user,
        state=WalletState.QUALIFIED,
    )

    all_cycle_based_org_setting_category_associations: list[
        ReimbursementOrgSettingCategoryAssociation
    ] = (
        db.session.query(ReimbursementOrgSettingCategoryAssociation)
        .filter(
            ReimbursementOrgSettingCategoryAssociation.reimbursement_organization_settings_id
            == wallet.reimbursement_organization_settings_id,
            ReimbursementOrgSettingCategoryAssociation.benefit_type
            == BenefitTypes.CYCLE,
        )
        .all()
    )
    assert len(all_cycle_based_org_setting_category_associations) == 0

    handle_wallet_state_change(wallet, WalletState.PENDING)

    credits_list: list[ReimbursementCycleCredits] = (
        db.session.query(ReimbursementCycleCredits)
        .filter(ReimbursementCycleCredits.reimbursement_wallet_id == wallet.id)
        .all()
    )

    assert len(credits_list) == 0


@pytest.mark.parametrize(
    "initial_state, note, wallet_id_offset",
    [
        pytest.param(
            WalletState.PENDING,
            f"Some note; {WALLET_QUALIFICATION_SERVICE_TAG}",
            1,
            id="Pending flag with valid note. Missing wallet",
        ),
        pytest.param(
            WalletState.QUALIFIED,
            f"Some note; {WALLET_QUALIFICATION_SERVICE_TAG}",
            0,
            id="Qualified flag with valid note.",
        ),
        pytest.param(
            WalletState.PENDING, "Some note", 0, id="Pending flag with invalid note."
        ),
    ],
)
def test_handle_qualification_of_wallet_created_by_wqs_invalid_conditions(
    enterprise_user,
    initial_state,
    note,
    wallet_id_offset,
):
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user,
        state=initial_state,
        note=note,
    )
    assert (
        handle_qualification_of_wallet_created_by_wqs(wallet.id + wallet_id_offset) == 1
    )


@pytest.mark.parametrize(
    "alegeus_success, process_historical_spend_wallets_return,  expected_state, expected_note, expected_zd_call_count, "
    "expected_zd_tag, expected_zd_called_by, expected_zd_ticket_id",
    [
        pytest.param(
            (True, []),
            [],
            WalletState.QUALIFIED,
            "Some note; creator: wallet_qualification_service; updater: wallet_qualification_rq_job. "
            "Successfully auto-qualified the wallet; ",
            0,
            None,
            None,
            None,
            id="alegeus_and_historic_spend_success",
        ),
        pytest.param(
            (False, [FLASH_MESSAGE]),
            None,
            WalletState.PENDING,
            "Some note; creator: wallet_qualification_service; updater: wallet_qualification_rq_job. "
            "Manual Action needed. Unable to auto-qualify the wallet. "
            "Reason:Error; Unable to configure wallet in Alegeus.; ",
            1,
            WALLET_APPLICATION_MANUAL_REVIEW_TAG,
            WQS_MONO_RQ_JOB,
            1234567,
            id="alegeus_config_failure",
        ),
        pytest.param(
            (True, []),
            [FLASH_MESSAGE],
            WalletState.PENDING,
            "Some note; creator: wallet_qualification_service; updater: wallet_qualification_rq_job. "
            "Manual Action needed. Unable to auto-qualify the wallet. "
            "Reason:Error processing historical wallet spend. Wallet state does not need to be rolled back.; ",
            1,
            WALLET_APPLICATION_MANUAL_REVIEW_TAG,
            WQS_MONO_RQ_JOB,
            7654321,
            id="historic_spend_failure",
        ),
    ],
)
def test_handle_qualification_of_wallet_created_by_wqs_alegeus_historic_spend(
    enterprise_user,
    ff_test_data,
    mock_historical_spend_enabled,
    alegeus_success,
    process_historical_spend_wallets_return,
    expected_state,
    expected_note,
    expected_zd_call_count,
    expected_zd_tag,
    expected_zd_called_by,
    expected_zd_ticket_id,
):
    mock_historical_spend_enabled(True)
    ros = ReimbursementOrganizationSettingsFactory.create(
        organization_id=enterprise_user.organization.id,
        direct_payment_enabled=True,
    )
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user,
        state=WalletState.PENDING,
        reimbursement_organization_settings=ros,
        note=f"Some note; {WALLET_QUALIFICATION_SERVICE_TAG}; ",
    )
    rwu: ReimbursementWalletUsers = ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id, user_id=enterprise_user.id
    )
    with patch(
        "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
        return_value=True,
    ), patch(
        "wallet.services.reimbursement_wallet_state_change.configure_wallet_in_alegeus",
        return_value=alegeus_success,
    ) as mock_configure_wallet_in_alegeus, patch(
        "wallet.services.reimbursement_wallet_state_change.assign_payments_customer_id_to_wallet"
    ) as mock_assign_payments_customer_id_to_wallet, patch(
        "wallet.config.use_alegeus_for_reimbursements", return_value=True
    ), patch(
        "wallet.services.wallet_historical_spend.WalletHistoricalSpendService.process_historical_spend_wallets",
        return_value=process_historical_spend_wallets_return,
    ), patch(
        "wallet.services.reimbursement_wallet_messaging.send_general_ticket_to_zendesk",
        return_value=expected_zd_ticket_id,
    ) as mock_send_general_ticket_to_zendesk:
        mock_configure_wallet_in_alegeus.return_value = alegeus_success

        res = handle_qualification_of_wallet_created_by_wqs(wallet.id)
        assert res == 0
        assert wallet.note == expected_note
        assert wallet.state == expected_state
        assert mock_assign_payments_customer_id_to_wallet.call_count == 1
        assert mock_send_general_ticket_to_zendesk.call_count == expected_zd_call_count
        if expected_zd_call_count:
            kwargs = mock_send_general_ticket_to_zendesk.call_args.kwargs
            assert expected_zd_tag in kwargs["tags"]
            assert kwargs["called_by"] == expected_zd_called_by
        assert rwu.zendesk_ticket_id == expected_zd_ticket_id


def get_affiliated_channel(wallet_id: int) -> Channel | None:
    return (
        db.session.query(Channel)
        .join(
            ReimbursementWalletUsers, Channel.id == ReimbursementWalletUsers.channel_id
        )
        .filter(ReimbursementWalletUsers.reimbursement_wallet_id == wallet_id)
        .scalar()
    )
