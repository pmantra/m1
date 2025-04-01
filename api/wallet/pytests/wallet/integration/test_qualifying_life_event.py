import datetime
from unittest.mock import patch

import requests

from wallet.services.reimbursement_qualifying_life_event import apply_qle_to_plan


def test_apply_qle_to_plan__success(
    valid_alegeus_plan_hra, qualified_alegeus_wallet_hra, valid_alegeus_account_hra
):
    def make_api_request_side_effect(url, data=None, **kwargs):
        assert data["accountTypeCode"] == "HRA"
        assert data["planId"] == "FAMILYFUND"
        assert data["annualElection"] == 500

        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: {}  # successful body is empty
        return mock_response

    with patch(
        "wallet.models.reimbursement.ReimbursementAccount.query"
    ) as reimbursement_account_query_mock, patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request:
        reimbursement_account_query_mock.filter_by.return_value.scalar.return_value = (
            valid_alegeus_account_hra
        )

        messages = apply_qle_to_plan(
            valid_alegeus_plan_hra, 500, datetime.datetime.now()
        )

        assert mock_request.call_count == 1
        assert len(messages) == 1
        assert messages[0].message.startswith("Successfully added QLE")


def test_apply_qle_to_plan__error(
    valid_alegeus_plan_hra, qualified_alegeus_wallet_hra, valid_alegeus_account_hra
):
    def make_api_request_side_effect(url, data=None, **kwargs):
        assert data["accountTypeCode"] == "HRA"
        assert data["planId"] == "FAMILYFUND"
        assert data["annualElection"] == 500

        mock_response = requests.Response()
        mock_response.status_code = 500
        mock_response.json = (
            lambda: "Error -2146233087, Plan is not enabled for Life Event Balance Management."
        )
        return mock_response

    with patch(
        "wallet.models.reimbursement.ReimbursementAccount.query"
    ) as reimbursement_account_query_mock, patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request:
        reimbursement_account_query_mock.filter_by.return_value.scalar.return_value = (
            valid_alegeus_account_hra
        )

        messages = apply_qle_to_plan(
            valid_alegeus_plan_hra, 500, datetime.datetime.now()
        )

        assert mock_request.call_count == 1
        assert len(messages) == 2
        assert messages[0].message.startswith("Unable to add QLE")
