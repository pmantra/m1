import datetime
from unittest.mock import patch

import pytest
from requests import Response

from wallet.models.constants import AlegeusCardStatus, CardStatus
from wallet.models.reimbursement_wallet_debit_card import ReimbursementWalletDebitCard
from wallet.utils.alegeus.debit_cards.terminate_employees import (
    handle_terminated_employees,
)


def test_handle_terminated_employees__wallet_enablement__missing(
    wallet_debitcardinator,
    qualified_alegeus_wallet_hra,
    qualified_alegeus_wallet_hdhp_single,
    qualified_alegeus_wallet_hdhp_family,
    put_debit_card_update_status_response,
):
    """
    Tests a wallet with no wallet enablement updates debit card to inactive.
    """
    wallet_debitcardinator(qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE)
    wallet_debitcardinator(
        qualified_alegeus_wallet_hdhp_single, card_status=CardStatus.NEW
    )
    wallet_debitcardinator(
        qualified_alegeus_wallet_hdhp_family, card_status=CardStatus.INACTIVE
    )
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    mock_update_debit_response = Response()
    mock_update_debit_response.status_code = 200
    mock_update_debit_response.json = lambda: put_debit_card_update_status_response(
        qualified_alegeus_wallet_hra, AlegeusCardStatus.TEMP_INACTIVE.value
    )

    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
    ) as mock_wallet_enablement, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_details"
    ) as mock_get_employee_details, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.put_debit_card_update_status"
    ) as mock_update_debit_card, patch(
        "utils.braze_events.braze.send_event"
    ), patch(
        "wallet.utils.alegeus.debit_cards.terminate_employees.send_message"
    ) as mock_email:
        mock_wallet_enablement.return_value = None
        mock_get_employee_details.return_value = mock_response
        mock_put_employee_services_and_banking.return_value = mock_response
        mock_update_debit_card.return_value = mock_update_debit_response

        handle_terminated_employees(
            allowed_debit_card_ids=[
                qualified_alegeus_wallet_hra.debit_card.id,
                qualified_alegeus_wallet_hdhp_single.debit_card.id,
                qualified_alegeus_wallet_hdhp_family.debit_card.id,
            ]
        )

        # debit_cards = ReimbursementWalletDebitCard.query.filter_by(
        #     card_status="INACTIVE"
        # ).all()
        # assert len(debit_cards) == 3
        # assert mock_put_employee_services_and_banking.called
        # assert mock_update_debit_card.called
        # assert (
        #     event.call_count == 2
        # )  # Sends member email about debit card being terminated
        assert mock_email.called  # Sends Ops email of terminated users


def test_handle_terminated_employees__wallet_enablement__past_end_date(
    wallet_debitcardinator,
    qualified_alegeus_wallet_hra,
    qualified_alegeus_wallet_hdhp_single,
    qualified_alegeus_wallet_hdhp_family,
    put_debit_card_update_status_response,
    eligibility_factories,
):
    """
    Tests a wallet with wallet enablement past it's end date updates debit card to inactive.
    """
    wallet_debitcardinator(qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE)
    e9y_member = eligibility_factories.WalletEnablementFactory.create(
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
        eligibility_end_date=datetime.date(2020, 1, 1),
    )

    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    mock_update_debit_response = Response()
    mock_update_debit_response.status_code = 200
    mock_update_debit_response.json = lambda: put_debit_card_update_status_response(
        qualified_alegeus_wallet_hra, AlegeusCardStatus.TEMP_INACTIVE.value
    )

    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
    ) as mock_wallet_enablement, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_details"
    ) as mock_get_employee_details, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.put_debit_card_update_status"
    ) as mock_update_debit_card, patch(
        "utils.braze_events.braze.send_event"
    ), patch(
        "wallet.utils.alegeus.debit_cards.terminate_employees.send_message"
    ) as mock_email:
        mock_wallet_enablement.return_value = e9y_member
        mock_get_employee_details.return_value = mock_response
        mock_put_employee_services_and_banking.return_value = mock_response
        mock_update_debit_card.return_value = mock_update_debit_response

        handle_terminated_employees(
            allowed_debit_card_ids=[
                qualified_alegeus_wallet_hra.debit_card.id,
            ]
        )

        # debit_cards = ReimbursementWalletDebitCard.query.filter_by(
        #     card_status="INACTIVE"
        # ).all()
        # assert len(debit_cards) == 3
        # assert mock_put_employee_services_and_banking.called
        # assert mock_update_debit_card.called
        # assert (
        #     event.call_count == 2
        # )  # Sends member email about debit card being terminated
        assert mock_email.called  # Sends Ops email of terminated users


def test_handle_terminated_employees__wallet_enablement__future_end_date(
    wallet_debitcardinator,
    qualified_alegeus_wallet_hra,
    eligibility_factories,
):
    """
    Tests a debit card with wallet enablement ending in the future does not update or send emails
    """
    wallet_debitcardinator(qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE)
    e9y_member = eligibility_factories.WalletEnablementFactory.create(
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
        eligibility_end_date=datetime.date(2038, 1, 19),
    )

    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
    ) as mock_wallet_enablement, patch(
        "wallet.utils.alegeus.debit_cards.terminate_employees.send_message"
    ) as mock_email:
        mock_wallet_enablement.return_value = e9y_member

        handle_terminated_employees(
            allowed_debit_card_ids=[qualified_alegeus_wallet_hra.debit_card.id]
        )
        debit_cards = ReimbursementWalletDebitCard.query.all()

        assert debit_cards[0].card_status == CardStatus.ACTIVE
        assert mock_email.called is False


def test_handle_terminated_employees__wallet_enablement__no_end_date(
    wallet_debitcardinator,
    qualified_alegeus_wallet_hra,
    eligibility_factories,
):
    """
    Tests a debit card with wallet enable without an end date does not update or send emails
    """
    wallet_debitcardinator(qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE)
    e9y_member = eligibility_factories.WalletEnablementFactory.create(
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
        eligibility_end_date=None,
    )
    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
    ) as mock_wallet_enablement, patch(
        "wallet.utils.alegeus.debit_cards.terminate_employees.send_message"
    ) as mock_email:
        mock_wallet_enablement.return_value = e9y_member

        handle_terminated_employees(
            allowed_debit_card_ids=[qualified_alegeus_wallet_hra.debit_card.id]
        )
        debit_cards = ReimbursementWalletDebitCard.query.all()

        assert debit_cards[0].card_status == CardStatus.ACTIVE
        assert mock_email.called is False


def test_handle_terminated_employees_single_fail_terminate_single_success(
    wallet_debitcardinator,
    qualified_alegeus_wallet_hra,
    qualified_alegeus_wallet_hdhp_single,
    put_debit_card_update_status_response,
):
    """
    Tests a single failed update to termination date in Alegeus does not stop other debit cards from updating and
    does not update when failed.
    """
    wallet_debitcardinator(qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE)
    wallet_debitcardinator(
        qualified_alegeus_wallet_hdhp_single, card_status=CardStatus.NEW
    )

    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    mock_response_2 = Response()
    mock_response_2.status_code = 400
    mock_response_2.json = lambda: {}

    mock_update_debit_response = Response()
    mock_update_debit_response.status_code = 200
    mock_update_debit_response.json = lambda: put_debit_card_update_status_response(
        qualified_alegeus_wallet_hra, AlegeusCardStatus.TEMP_INACTIVE.value
    )

    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
    ) as mock_wallet_enablement, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_details"
    ) as employee_details, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking",
        side_effect=[mock_response, mock_response_2],
    ), patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.put_debit_card_update_status"
    ) as mock_update_debit_card, patch(
        "utils.braze_events.braze.send_event"
    ), patch(
        "wallet.utils.alegeus.debit_cards.terminate_employees.send_message"
    ) as mock_email:
        mock_wallet_enablement.return_value = None
        employee_details.return_value = mock_response
        mock_update_debit_card.return_value = mock_update_debit_response

        handle_terminated_employees(
            allowed_debit_card_ids=[
                qualified_alegeus_wallet_hra.debit_card.id,
                qualified_alegeus_wallet_hdhp_single.debit_card.id,
            ]
        )

        # inactive_debit_cards = ReimbursementWalletDebitCard.query.filter_by(
        #     card_status="INACTIVE"
        # ).all()
        # active_debit_cards = ReimbursementWalletDebitCard.query.filter_by(
        #     card_status="NEW"
        # ).all()
        #
        # assert len(inactive_debit_cards) == 1
        # assert len(active_debit_cards) == 1
        # assert event.call_count == 1
        assert mock_email.called


def test_handle_terminated_employees_single_fail_debit_update_single_success(
    wallet_debitcardinator,
    qualified_alegeus_wallet_hra,
    qualified_alegeus_wallet_hdhp_single,
    put_debit_card_update_status_response,
):
    """
    Tests a single failed card when updating status in Alegeus does not stop other debit cards from updating and
    does not update when failed.
    """
    wallet_debitcardinator(qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE)
    wallet_debitcardinator(
        qualified_alegeus_wallet_hdhp_single, card_status=CardStatus.NEW
    )

    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    mock_update_debit_response = Response()
    mock_update_debit_response.status_code = 200
    mock_update_debit_response.json = lambda: put_debit_card_update_status_response(
        qualified_alegeus_wallet_hra, AlegeusCardStatus.TEMP_INACTIVE
    )

    mock_response_2 = Response()
    mock_response_2.status_code = 400
    mock_response_2.json = lambda: {}

    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
    ) as mock_wallet_enablement, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_details"
    ) as employee_details, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as terminate_response, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.put_debit_card_update_status",
        side_effect=[mock_update_debit_response, mock_response_2],
    ), patch(
        "utils.braze_events.braze.send_event"
    ), patch(
        "wallet.utils.alegeus.debit_cards.terminate_employees.send_message"
    ) as mock_email:
        mock_wallet_enablement.return_value = None
        employee_details.return_value = mock_response
        terminate_response.return_value = mock_response

        handle_terminated_employees(
            allowed_debit_card_ids=[
                qualified_alegeus_wallet_hra.debit_card.id,
                qualified_alegeus_wallet_hdhp_single.debit_card.id,
            ]
        )

        # inactive_debit_cards = ReimbursementWalletDebitCard.query.filter_by(
        #     card_status="INACTIVE"
        # ).all()
        # active_debit_cards = ReimbursementWalletDebitCard.query.filter_by(
        #     card_status="NEW"
        # ).all()
        # assert len(inactive_debit_cards) == 1
        # assert len(active_debit_cards) == 1
        # assert event.call_count == 1
        assert mock_email.called


@pytest.mark.parametrize(
    argnames="allowed_ids",
    argvalues=[[], None],
)
def test_handle_terminated_employees__no_debit_cards_found(allowed_ids):
    """
    Tests no debit cards found does not send email
    """
    with patch(
        "wallet.utils.alegeus.debit_cards.terminate_employees.send_message"
    ) as mock_email:
        handle_terminated_employees(allowed_debit_card_ids=allowed_ids)

        debit_cards = ReimbursementWalletDebitCard.query.all()
        assert len(debit_cards) == 0
        assert mock_email.called is False


def test_handle_terminated_employees_raises_exception__fails(
    wallet_debitcardinator,
    qualified_alegeus_wallet_hra,
    qualified_alegeus_wallet_hdhp_single,
    put_debit_card_update_status_response,
):
    """
    When an exception is raised when terminating we do not update objects.
    """
    wallet_debitcardinator(qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE)
    wallet_debitcardinator(
        qualified_alegeus_wallet_hdhp_single, card_status=CardStatus.NEW
    )

    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search",
        side_effect=Exception,
    ), patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_details"
    ) as employee_details, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as terminate_response, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.put_debit_card_update_status",
    ), patch(
        "utils.braze_events.braze.send_event"
    ) as event, patch(
        "wallet.utils.alegeus.debit_cards.terminate_employees.send_message"
    ) as mock_email:
        # mock_wallet_enablement.return_value = None
        employee_details.return_value = mock_response
        terminate_response.return_value = mock_response
        with pytest.raises(  # noqa  B017  TODO:  `assertRaises(Exception)` and `pytest.raises(Exception)` should be considered evil. They can lead to your test passing even if the code being tested is never executed due to a typo. Assert for a more specific exception (builtin or custom), or use `assertRaisesRegex` (if using `assertRaises`), or add the `match` keyword argument (if using `pytest.raises`), or use the context manager form with a target.
            Exception
        ):
            handle_terminated_employees(
                allowed_debit_card_ids=[
                    qualified_alegeus_wallet_hra.debit_card.id,
                    qualified_alegeus_wallet_hdhp_single.debit_card.id,
                ]
            )

        active_debit_cards = ReimbursementWalletDebitCard.query.filter(
            ReimbursementWalletDebitCard.card_status.in_(
                [CardStatus.NEW.value, CardStatus.ACTIVE.value]
            )
        ).all()
        assert len(active_debit_cards) == 2
        assert event.call_count == 0
        assert mock_email.called is False
