from unittest.mock import PropertyMock, patch

import pytest
import requests

from wallet.models.constants import (
    ReimbursementMethod,
    ReimbursementRequestState,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)


@pytest.fixture(scope="function")
def qualified_wallet():
    wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED,
        reimbursement_organization_settings__allowed_reimbursement_categories=[
            ("fertility", 5000, None),
            ("other", 3000, None),
        ],
        reimbursement_method=ReimbursementMethod.PAYROLL,
    )
    return wallet


@pytest.fixture(scope="function")
def reimbursement_wallet_user(
    enterprise_user, qualified_wallet
) -> ReimbursementWalletUsers:
    return ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=qualified_wallet.id,
        type=WalletUserType.DEPENDENT,
        status=WalletUserStatus.ACTIVE,
    )


@pytest.fixture()
def get_ach_accounts_200_with_account():
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {
            "BankAccountKey": -1,
            "BankAccountName": "checking",
            "BankAccountNumber": "0037308343",
        }
    ]
    return mock_response


@pytest.fixture()
def get_ach_accounts_200_without_account():
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: []
    return mock_response


def test_user_reimbursement_wallet_bank_account__get_success(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_with_account,
    reimbursement_wallet_user,
):
    expected_bank_account_info = {
        "bank_name": "checking",
        "last4": "8343",
        "country": "",
    }
    with patch(
        "wallet.models.reimbursement_wallet.ReimbursementWallet.employee_member",
        new_callable=PropertyMock,
    ) as mock_employee_member:
        with patch(
            "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
        ) as mock_get_ach_accounts:
            mock_employee_member.return_value = enterprise_user
            mock_get_ach_accounts.return_value = get_ach_accounts_200_with_account

            res = client.get(
                f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
                headers=api_helpers.json_headers(qualified_wallet.employee_member),
            )

            content = api_helpers.load_json(res)
            assert res.status_code == 200
            assert content == expected_bank_account_info


def test_user_reimbursement_wallet_bank_account__get_fail_no_bank_account_for_user(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_without_account,
    reimbursement_wallet_user,
):
    qualified_wallet.member = enterprise_user

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts:
        mock_get_ach_accounts.return_value = get_ach_accounts_200_without_account

        res = client.get(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(qualified_wallet.member),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 404
        assert content["message"] == "You do not have an attached bank account!"


def test_user_reimbursement_wallet_bank_account__get_fail_error_retrieving_info_from_alegeus(
    client, api_helpers, qualified_wallet, enterprise_user, reimbursement_wallet_user
):
    qualified_wallet.member = enterprise_user

    mock_response = requests.Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts:
        mock_get_ach_accounts.return_value = mock_response

        res = client.get(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(qualified_wallet.member),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 404
        assert (
            content["message"]
            == f"Could not find bank accounts for User ID={enterprise_user.id}"
        )


def test_user_reimbursement_wallet_bank_account__post_success(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_with_account,
    get_ach_accounts_200_without_account,
    qualified_wallet_enablement_hdhp_single,
):
    qualified_wallet.member = enterprise_user

    bank_account_number = "0037308343"
    bank_routing_number = "064000017"
    bank_account_type_code = "CHECKING"
    bank_name = "checking"

    mock_put_response = requests.Response()
    mock_put_response.status_code = 200
    mock_put_response.json = lambda: {}

    expected_bank_account_info = {
        "bank_name": "checking",
        "last4": "8343",
        "country": "",
    }

    mock_translate_response = qualified_wallet_enablement_hdhp_single

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search"
    ) as mock_translate:
        mock_get_ach_accounts.side_effect = [
            get_ach_accounts_200_without_account,
            get_ach_accounts_200_with_account,
        ]
        mock_put_employee_services_and_banking.return_value = mock_put_response

        mock_translate.return_value = mock_translate_response

        res = client.post(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(qualified_wallet.member),
            data=api_helpers.json_data(
                {
                    "BankAcctName": bank_name,
                    "BankAccount": bank_account_number,
                    "BankRoutingNumber": bank_routing_number,
                    "BankAccountTypeCode": bank_account_type_code,
                }
            ),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 201
        assert content == expected_bank_account_info


def test_user_reimbursement_wallet_bank_account__post_fail_user_already_has_bank_account(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_with_account,
    reimbursement_wallet_user,
):
    qualified_wallet.member = enterprise_user

    bank_account_number = "0037308343"
    bank_routing_number = "064000017"
    bank_account_type_code = "CHECKING"
    bank_name = "checking"

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking:
        mock_get_ach_accounts.return_value = get_ach_accounts_200_with_account
        mock_put_employee_services_and_banking.return_value = requests.Response()
        mock_put_employee_services_and_banking.return_value.status_code = 200

        res = client.post(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(qualified_wallet.member),
            data=api_helpers.json_data(
                {
                    "BankAcctName": bank_name,
                    "BankAccount": bank_account_number,
                    "BankRoutingNumber": bank_routing_number,
                    "BankAccountTypeCode": bank_account_type_code,
                }
            ),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 409
        assert content["message"].startswith(
            "Whoops! You already have a bank account on file"
        )


def test_user_reimbursement_wallet_bank_account__post_fail_error_setting_bank_account(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_without_account,
    qualified_wallet_enablement_hdhp_single,
):
    qualified_wallet.member = enterprise_user

    bank_account_number = "0037308343"
    bank_routing_number = "064000017"
    bank_account_type_code = "CHECKING"
    bank_name = "checking"

    mock_response = requests.Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    mock_translate_response = qualified_wallet_enablement_hdhp_single

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search"
    ) as mock_translate:
        mock_get_ach_accounts.return_value = get_ach_accounts_200_without_account
        mock_put_employee_services_and_banking.return_value = mock_response

        mock_translate.return_value = mock_translate_response

        res = client.post(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(qualified_wallet.member),
            data=api_helpers.json_data(
                {
                    "BankAcctName": bank_name,
                    "BankAccount": bank_account_number,
                    "BankRoutingNumber": bank_routing_number,
                    "BankAccountTypeCode": bank_account_type_code,
                }
            ),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 400
        assert (
            content["message"]
            == f"Could not update banking info for Wallet ID={qualified_wallet.id}"
        )


def test_user_reimbursement_wallet_bank_account__post_fail_bank_account_not_in_alegeus_after_setting(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_with_account,
    get_ach_accounts_200_without_account,
    qualified_wallet_enablement_hdhp_single,
):
    qualified_wallet.member = enterprise_user

    bank_account_number = "0037308343"
    bank_routing_number = "064000017"
    bank_account_type_code = "CHECKING"
    bank_name = "checking"

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    mock_translate_response = qualified_wallet_enablement_hdhp_single

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search"
    ) as mock_translate:
        mock_get_ach_accounts.return_value = get_ach_accounts_200_without_account
        mock_put_employee_services_and_banking.return_value = mock_response

        mock_translate.return_value = mock_translate_response

        res = client.post(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(qualified_wallet.member),
            data=api_helpers.json_data(
                {
                    "BankAcctName": bank_name,
                    "BankAccount": bank_account_number,
                    "BankRoutingNumber": bank_routing_number,
                    "BankAccountTypeCode": bank_account_type_code,
                }
            ),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 400
        assert content["message"] == "Error updating bank account!"


def test_user_reimbursement_wallet_bank_account__put_success(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_with_account,
    qualified_wallet_enablement_hdhp_single,
):
    qualified_wallet.member = enterprise_user

    bank_account_number = "0037308343"
    bank_routing_number = "064000017"
    bank_account_type_code = "CHECKING"
    bank_name = "checking"

    mock_put_response = requests.Response()
    mock_put_response.status_code = 200
    mock_put_response.json = lambda: {}

    expected_bank_account_info = {
        "bank_name": "checking",
        "last4": "8343",
        "country": "",
    }

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search"
    ) as mock_translate:
        mock_get_ach_accounts.return_value = get_ach_accounts_200_with_account
        mock_put_employee_services_and_banking.return_value = mock_put_response

        mock_translate.return_value = qualified_wallet_enablement_hdhp_single

        res = client.put(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(qualified_wallet.member),
            data=api_helpers.json_data(
                {
                    "BankAcctName": bank_name,
                    "BankAccount": bank_account_number,
                    "BankRoutingNumber": bank_routing_number,
                    "BankAccountTypeCode": bank_account_type_code,
                }
            ),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 200
        assert content == expected_bank_account_info


def test_user_reimbursement_wallet_bank_account__put_fail_error_setting_bank_account(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_without_account,
    qualified_wallet_enablement_hdhp_single,
):
    qualified_wallet.member = enterprise_user

    bank_account_number = "0037308343"
    bank_routing_number = "064000017"
    bank_account_type_code = "CHECKING"
    bank_name = "checking"

    mock_response = requests.Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search"
    ) as mock_translate:
        mock_get_ach_accounts.return_value = get_ach_accounts_200_without_account
        mock_put_employee_services_and_banking.return_value = mock_response

        mock_translate.return_value = qualified_wallet_enablement_hdhp_single

        res = client.put(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(qualified_wallet.member),
            data=api_helpers.json_data(
                {
                    "BankAcctName": bank_name,
                    "BankAccount": bank_account_number,
                    "BankRoutingNumber": bank_routing_number,
                    "BankAccountTypeCode": bank_account_type_code,
                }
            ),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 400
        assert (
            content["message"]
            == f"Could not update banking info for Wallet ID={qualified_wallet.id}"
        )


def test_user_reimbursement_wallet_bank_account__put_fail_bank_account_not_in_alegeus_after_setting(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_with_account,
    get_ach_accounts_200_without_account,
    qualified_wallet_enablement_hdhp_single,
):
    qualified_wallet.member = enterprise_user

    bank_account_number = "0037308343"
    bank_routing_number = "064000017"
    bank_account_type_code = "CHECKING"
    bank_name = "checking"

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search"
    ) as mock_translate:

        mock_translate.return_value = qualified_wallet_enablement_hdhp_single

        mock_get_ach_accounts.return_value = get_ach_accounts_200_without_account
        mock_put_employee_services_and_banking.return_value = mock_response

        res = client.put(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(qualified_wallet.member),
            data=api_helpers.json_data(
                {
                    "BankAcctName": bank_name,
                    "BankAccount": bank_account_number,
                    "BankRoutingNumber": bank_routing_number,
                    "BankAccountTypeCode": bank_account_type_code,
                }
            ),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 400
        assert content["message"] == "Error updating bank account!"


def test_user_reimbursement_wallet_bank_account__delete_success(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_without_account,
    qualified_wallet_enablement_hdhp_single,
):
    qualified_wallet.member = enterprise_user

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.send_general_ticket_to_zendesk"
    ) as zd_task, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search"
    ) as mock_translate:
        mock_translate.return_value = qualified_wallet_enablement_hdhp_single

        mock_get_ach_accounts.return_value = get_ach_accounts_200_without_account
        mock_put_employee_services_and_banking.return_value = mock_response

        res = client.delete(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(enterprise_user),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 200
        assert zd_task.call_count == 0
        assert content["message"] == "Removed a bank account."


def test_user_reimbursement_wallet_bank_account__delete_success_with_reimbursed_requests(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_without_account,
    qualified_wallet_enablement_hdhp_single,
):
    qualified_wallet.member = enterprise_user

    category = qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    ReimbursementRequestFactory.create(
        amount=50,
        reimbursement_wallet_id=qualified_wallet.id,
        reimbursement_request_category_id=category.id,
        state=ReimbursementRequestState.REIMBURSED,
    )

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.send_general_ticket_to_zendesk"
    ) as zd_task, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search"
    ) as mock_translate:
        mock_translate.return_value = qualified_wallet_enablement_hdhp_single

        mock_get_ach_accounts.return_value = get_ach_accounts_200_without_account
        mock_put_employee_services_and_banking.return_value = mock_response

        res = client.delete(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(enterprise_user),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 200
        assert zd_task.call_count == 0
        assert content["message"] == "Removed a bank account."


def test_user_reimbursement_wallet_bank_account__delete_fail_direct_deposit(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_without_account,
    reimbursement_wallet_user,
):
    qualified_wallet.member = enterprise_user
    qualified_wallet.reimbursement_method = ReimbursementMethod.DIRECT_DEPOSIT

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.send_general_ticket_to_zendesk"
    ) as zd_task, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking:
        mock_get_ach_accounts.return_value = get_ach_accounts_200_without_account
        mock_put_employee_services_and_banking.return_value = mock_response

        res = client.delete(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(enterprise_user),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 409
        assert zd_task.call_count == 0
        assert (
            content["message"]
            == "Unable to remove a bank account when the reimbursement method is direct deposit."
        )


def test_user_reimbursement_wallet_bank_account__delete_fail_requests_in_flight(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_without_account,
    reimbursement_wallet_user,
):
    qualified_wallet.member = enterprise_user

    category = qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    ReimbursementRequestFactory.create(
        amount=50,
        reimbursement_wallet_id=qualified_wallet.id,
        reimbursement_request_category_id=category.id,
        state=ReimbursementRequestState.PENDING,
    )

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.send_general_ticket_to_zendesk"
    ) as zd_task, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking:
        mock_get_ach_accounts.return_value = get_ach_accounts_200_without_account
        mock_put_employee_services_and_banking.return_value = mock_response

        res = client.delete(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(qualified_wallet.member),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 200
        assert content["message"].startswith(
            "This bank account cannot be removed automatically "
            "due to reimbursement requests in flight. "
        )
        assert zd_task.call_count == 1


def test_user_reimbursement_wallet_bank_account__delete_fail_error_removing_bank_account(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_with_account,
    qualified_wallet_enablement_hdhp_single,
):
    qualified_wallet.member = enterprise_user

    mock_response = requests.Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.send_general_ticket_to_zendesk"
    ) as zd_task, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search"
    ) as mock_translate:
        mock_translate.return_value = qualified_wallet_enablement_hdhp_single
        mock_get_ach_accounts.return_value = get_ach_accounts_200_with_account
        mock_put_employee_services_and_banking.return_value = mock_response

        res = client.delete(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(enterprise_user),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 400
        assert zd_task.call_count == 0
        assert (
            content["message"]
            == f"Could not update banking info for Wallet ID={qualified_wallet.id}"
        )


def test_user_reimbursement_wallet_bank_account__delete_fail_bank_account_still_in_alegeus_after_setting(
    client,
    api_helpers,
    qualified_wallet,
    enterprise_user,
    get_ach_accounts_200_with_account,
    qualified_wallet_enablement_hdhp_single,
):
    qualified_wallet.member = enterprise_user

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch(
        "wallet.resources.reimbursement_wallet_bank_account.send_general_ticket_to_zendesk"
    ) as zd_task, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.get_ach_accounts"
    ) as mock_get_ach_accounts, patch(
        "wallet.resources.reimbursement_wallet_bank_account.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_employee_services_and_banking, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search"
    ) as mock_translate:
        mock_translate.return_value = qualified_wallet_enablement_hdhp_single
        mock_get_ach_accounts.return_value = get_ach_accounts_200_with_account
        mock_put_employee_services_and_banking.return_value = mock_response

        res = client.delete(
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}/bank_account",
            headers=api_helpers.json_headers(qualified_wallet.member),
        )

        content = api_helpers.load_json(res)
        assert res.status_code == 400
        assert zd_task.call_count == 1
        assert len(content["errors"]) == 1
        assert content["errors"][0]["detail"] == "Error updating bank account!"
