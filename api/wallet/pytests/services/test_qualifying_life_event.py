import datetime
from unittest.mock import patch

import requests

from wallet.services.reimbursement_qualifying_life_event import apply_qle_to_plan


def test_apply_qle_to_plan__success(
    valid_alegeus_plan_hra, qualified_alegeus_wallet_hra, valid_alegeus_account_hra
):
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}  # response body ignored

    with patch(
        "wallet.models.reimbursement.ReimbursementAccount.query"
    ) as reimbursement_account_query_mock, patch(
        "wallet.services.reimbursement_qualifying_life_event.AlegeusApi.post_add_qle",
        return_value=mock_response,
    ) as mock_request:
        reimbursement_account_query_mock.filter_by.return_value.scalar.return_value = (
            valid_alegeus_account_hra
        )

        amount = 500
        effective_date = datetime.datetime.now()

        messages = apply_qle_to_plan(valid_alegeus_plan_hra, amount, effective_date)

        assert mock_request.call_count == 1
        mock_request.assert_called_with(
            qualified_alegeus_wallet_hra, valid_alegeus_plan_hra, amount, effective_date
        )
        assert len(messages) == 1
        assert messages[0].message.startswith("Successfully added QLE")


def test_apply_qle_to_plan__error(
    valid_alegeus_plan_hra, qualified_alegeus_wallet_hra, valid_alegeus_account_hra
):
    mock_response = requests.Response()
    mock_response.status_code = 500
    mock_response.json = (
        lambda: "Error -2146233087, Plan is not enabled for Life Event Balance Management."
    )

    with patch(
        "wallet.models.reimbursement.ReimbursementAccount.query"
    ) as reimbursement_account_query_mock, patch(
        "wallet.services.reimbursement_qualifying_life_event.AlegeusApi.post_add_qle",
        return_value=mock_response,
    ) as mock_request:
        reimbursement_account_query_mock.filter_by.return_value.scalar.return_value = (
            valid_alegeus_account_hra
        )

        amount = 500
        effective_date = datetime.datetime.now()

        messages = apply_qle_to_plan(valid_alegeus_plan_hra, amount, effective_date)

        assert mock_request.call_count == 1
        mock_request.assert_called_with(
            qualified_alegeus_wallet_hra, valid_alegeus_plan_hra, amount, effective_date
        )
        assert len(messages) == 2
        assert messages[0].message.startswith("Unable to add QLE")
