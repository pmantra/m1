from unittest.mock import patch

from wallet.services.reimbursement_wallet_debit_card import remove_mobile_number


def test_remove_mobile_number__no_wallet(enterprise_user):
    with patch(
        "wallet.services.reimbursement_wallet_debit_card.remove_phone_number_from_alegeus"
    ) as remove_request:
        success = remove_mobile_number(enterprise_user, "202-555-1212")
        assert success is True
        assert remove_request.call_count == 0


def test_remove_mobile_number__no_debit_card(qualified_alegeus_wallet_hra):
    user = qualified_alegeus_wallet_hra.member

    with patch(
        "wallet.services.reimbursement_wallet_debit_card.remove_phone_number_from_alegeus"
    ) as remove_request:
        success = remove_mobile_number(user, "202-555-1212")
        assert success is True
        assert remove_request.call_count == 0


def test_remove_mobile_number__remove_error(
    qualified_alegeus_wallet_hra, wallet_debitcardinator
):
    wallet_debitcardinator(qualified_alegeus_wallet_hra)
    user = qualified_alegeus_wallet_hra.member

    with patch(
        "wallet.services.reimbursement_wallet_debit_card.remove_phone_number_from_alegeus"
    ) as remove_request:
        remove_request.return_value = False

        success = remove_mobile_number(user, "202-555-1212")

        assert success is False
        assert remove_request.call_count == 1


def test_remove_mobile_number__add_partial_error(
    qualified_alegeus_wallet_hra,
    qualified_alegeus_wallet_hdhp_single,
    wallet_debitcardinator,
):
    wallet_debitcardinator(qualified_alegeus_wallet_hra)
    wallet_debitcardinator(qualified_alegeus_wallet_hdhp_single)
    user = qualified_alegeus_wallet_hra.member

    def remove_request_side_effect(wallet, phone_number):
        return wallet is qualified_alegeus_wallet_hdhp_single

    with patch(
        "wallet.services.reimbursement_wallet_debit_card.remove_phone_number_from_alegeus"
    ) as remove_request:

        remove_request.side_effect = remove_request_side_effect

        success = remove_mobile_number(user, "202-555-1212")

        assert success is False
        assert remove_request.call_count == 2


def test_remove_mobile_number__success(
    qualified_alegeus_wallet_hra,
    qualified_alegeus_wallet_hdhp_single,
    wallet_debitcardinator,
):
    wallet_debitcardinator(qualified_alegeus_wallet_hra)
    wallet_debitcardinator(qualified_alegeus_wallet_hdhp_single)
    user = qualified_alegeus_wallet_hra.member

    with patch(
        "wallet.services.reimbursement_wallet_debit_card.remove_phone_number_from_alegeus"
    ) as remove_request:

        remove_request.return_value = True

        success = remove_mobile_number(user, "202-555-1212")

        assert success is True
        assert remove_request.call_count == 2
