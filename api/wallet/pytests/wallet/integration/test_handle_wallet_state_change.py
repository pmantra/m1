from unittest.mock import patch

import pytest
import requests

from wallet.alegeus_api import ALEGEUS_WCA_URL, ALEGEUS_WCP_URL
from wallet.models.constants import AllowedMembers, WalletState
from wallet.models.reimbursement import ReimbursementAccount
from wallet.pytests.factories import ReimbursementAccountTypeFactory
from wallet.services.reimbursement_wallet_state_change import (
    handle_wallet_settings_change,
    handle_wallet_state_change,
)
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory


# Blanket-patch the tests in this file to return a valid e9y record for the enterprise user
# that wallet fixtures are based on when getting the first & last name.
@pytest.fixture(autouse=True)
def patch_wallet_e9y(enterprise_user, eligibility_factories):
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user"
    ) as p:
        p.return_value = eligibility_factories.VerificationFactory.create(
            user_id=1,
            organization_id=enterprise_user.organization_employee.organization_id,
            first_name=enterprise_user.first_name,
            last_name=enterprise_user.last_name,
        )
        yield p


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_wallet_state_change__success_qualified_new_single_hra(
    qualified_alegeus_wallet_hra,
    qualified_wallet_enablement_hra,
    get_employee_accounts_list_response_hra,
):
    """
    A single employee with an HRA that has no current records in Alegeus
    Should create the employee and account records.
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = method + ":" + url

        # get_employee_demographic
        if key == f"GET:{ALEGEUS_WCP_URL}/participant/employee/enrollment/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: None
        # post_employee_services_and_banking
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # post_add_employee_account
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Account/None/123/456":
            assert data["employerId"] == "123"
            assert data["employeeId"] == "456"
            assert data["accountTypeCode"] == "HRA"
            assert data["originalPrefundedAmount"] == 50.0

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # get_account_summary
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/accounts/summary/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: get_employee_accounts_list_response_hra

        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request, patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search",
        return_value=qualified_wallet_enablement_hra,
    ):
        old_state = WalletState.PENDING

        handle_wallet_state_change(qualified_alegeus_wallet_hra, old_state)

        assert mock_request.call_count == 4
        assert (
            ReimbursementAccount.query.one().reimbursement_wallet_id
            == qualified_alegeus_wallet_hra.id
        )


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_wallet_state_change__success_qualified_new_hdhp_family(
    qualified_alegeus_wallet_with_dependents,
    qualified_wallet_enablement_hdhp_family,
    get_employee_accounts_list_response_hdhp_family,
):
    """
    An employee with dependents and a HDHP that has no current records in Alegeus
    Should create the employee, dependent, and account records.
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = method + ":" + url

        # get_employee_demographic
        if key == f"GET:{ALEGEUS_WCP_URL}/participant/employee/enrollment/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: None
        # post_employee_services_and_banking
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # get_dependents
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/dependent/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: []
        # post_dependent_services (called twice)
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Dependent/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # post_add_employee_account
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Account/None/123/456":
            assert data["employerId"] == "123"
            assert data["employeeId"] == "456"
            assert data["accountTypeCode"] == "DTR"
            assert data["originalPrefundedAmount"] == 0
            assert data["coverageTierId"] == "FAMILY"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # get_account_summary
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/accounts/summary/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: get_employee_accounts_list_response_hdhp_family
        # post_link_dependent_to_employee_account (called twice)
        elif (
            key
            == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Account/DependentAccount/None/123/456"
        ):
            assert data["accountTypeCode"] == "DTR"
            assert data["planId"] == "HDHP"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored

        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search",
        return_value=qualified_wallet_enablement_hdhp_family,
    ):
        old_state = WalletState.PENDING

        handle_wallet_state_change(qualified_alegeus_wallet_with_dependents, old_state)

        assert mock_request.call_count == 9
        assert (
            ReimbursementAccount.query.one().reimbursement_wallet_id
            == qualified_alegeus_wallet_with_dependents.id
        )


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_wallet_state_change__success_qualified_existing_hdhp_family(
    qualified_alegeus_wallet_with_dependents,
    qualified_wallet_enablement_hdhp_family,
    valid_alegeus_account_hdhp,
    get_employee_demographic_response,
    get_employee_dependents_list_response,
    get_employee_accounts_list_response_hdhp_family,
):
    """
    An employee with dependents and a HDHP that has all current records in Alegeus
    Should not create any new records.
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = method + ":" + url

        # get_employee_demographic
        if key == f"GET:{ALEGEUS_WCP_URL}/participant/employee/enrollment/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: get_employee_demographic_response(
                qualified_alegeus_wallet_with_dependents
            )
        # get_dependents
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/dependent/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: get_employee_dependents_list_response(
                qualified_alegeus_wallet_with_dependents
            )
        # get_account_details
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/accounts/details/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored

        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search",
        return_value=qualified_wallet_enablement_hdhp_family,
    ), patch(
        "wallet.models.reimbursement.ReimbursementAccount.query"
    ) as reimbursement_account_query_mock:
        reimbursement_account_query_mock.filter_by.return_value.scalar.return_value = (
            valid_alegeus_account_hdhp
        )

        old_state = WalletState.PENDING

        handle_wallet_state_change(qualified_alegeus_wallet_with_dependents, old_state)

        assert mock_request.call_count == 3


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_wallet_state_change__success_qualified_existing_hdhp_account_with_a_new_hdhp_plan(
    qualified_alegeus_wallet_with_two_hdhp_plans,
    qualified_wallet_enablement_hdhp_family,
    get_employee_accounts_list_response_hdhp_family,
    get_employee_accounts_list_response_hdhp_family_with_two_plans,
    get_employee_demographic_response,
    valid_alegeus_account_hdhp,
):
    """
    An employee without dependents and an account that has a current HDHP plan in Alegeus and adding a new HDHP
    Should ignore one plan and create a single, new employee, and account.
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = method + ":" + url
        # get_employee_demographic
        if key == f"GET:{ALEGEUS_WCP_URL}/participant/employee/enrollment/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: get_employee_demographic_response(
                qualified_alegeus_wallet_with_two_hdhp_plans
            )
        # get_account_details
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/accounts/details/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # post_add_employee_account
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Account/None/123/456":
            assert data["employerId"] == "123"
            assert data["employeeId"] == "456"
            assert data["accountTypeCode"] == "DTR"
            assert data["originalPrefundedAmount"] == 0
            assert data["coverageTierId"] == "FAMILY"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # get_account_summary
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/accounts/summary/None/123/456":
            mock_response.status_code = 200
            mock_response.json = (
                lambda: get_employee_accounts_list_response_hdhp_family_with_two_plans
            )

        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search",
        return_value=qualified_wallet_enablement_hdhp_family,
    ), patch(
        "wallet.models.reimbursement.ReimbursementAccount.query",
    ) as reimbursement_account_query_mock, patch(
        "wallet.models.reimbursement.ReimbursementAccountType.query"
    ) as reimbursement_account_type_mock:
        reimbursement_account_query_mock.filter_by.return_value.scalar.side_effect = [
            valid_alegeus_account_hdhp,
            None,
            None,
        ]
        reimbursement_account_type_mock.filter_by.return_value.one.return_value = (
            ReimbursementAccountTypeFactory.create(alegeus_account_type="DTR")
        )

        handle_wallet_settings_change(qualified_alegeus_wallet_with_two_hdhp_plans)

        assert mock_request.call_count == 4
        assert reimbursement_account_query_mock.filter_by.call_count == 3


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_wallet_state_change__success_qualified_partial_hdhp_family(
    qualified_alegeus_wallet_with_dependents,
    qualified_wallet_enablement_hdhp_family,
    valid_alegeus_account_hdhp,
    get_employee_demographic_response,
    get_employee_dependents_list_response,
    get_employee_accounts_list_response_hdhp_family,
):
    """
    An employee with dependents and a HDHP that has some records in Alegeus
    Should create one dependent, account.
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = method + ":" + url

        # get_employee_demographic
        if key == f"GET:{ALEGEUS_WCP_URL}/participant/employee/enrollment/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: get_employee_demographic_response(
                qualified_alegeus_wallet_with_dependents
            )
        # get_dependents
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/dependent/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: [
                get_employee_dependents_list_response(
                    qualified_alegeus_wallet_with_dependents
                )[0]
            ]  # new list with only first dependent
        # post_dependent_services (called once)
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Dependent/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # get_account_details
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/accounts/details/None/123/456":
            mock_response.status_code = 404
        # post_add_employee_account
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Account/None/123/456":
            assert data["employerId"] == "123"
            assert data["employeeId"] == "456"
            assert data["accountTypeCode"] == "DTR"
            assert data["originalPrefundedAmount"] == 0
            assert data["coverageTierId"] == "FAMILY"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # post_link_dependent_to_employee_account (called twice)
        elif (
            key
            == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Account/DependentAccount/None/123/456"
        ):
            assert data["accountTypeCode"] == "DTR"
            assert data["planId"] == "HDHP"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored

        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search",
        return_value=qualified_wallet_enablement_hdhp_family,
    ), patch(
        "wallet.models.reimbursement.ReimbursementAccount.query"
    ) as reimbursement_account_query_mock:
        reimbursement_account_query_mock.filter_by.return_value.scalar.return_value = (
            valid_alegeus_account_hdhp
        )

        old_state = WalletState.PENDING

        handle_wallet_state_change(qualified_alegeus_wallet_with_dependents, old_state)

        assert mock_request.call_count == 7


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_wallet_state_change__error_create_employee(
    qualified_alegeus_wallet_hra, qualified_wallet_enablement_hra
):
    """
    Failure to create employee record will stop process
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = method + ":" + url

        # get_employee_demographic
        if key == f"GET:{ALEGEUS_WCP_URL}/participant/employee/enrollment/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: None
        # post_employee_services_and_banking
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 500
            mock_response.json = lambda: {}  # response body is ignored

        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request, patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search",
        return_value=qualified_wallet_enablement_hra,
    ):
        old_state = WalletState.PENDING

        handle_wallet_state_change(qualified_alegeus_wallet_hra, old_state)

        assert mock_request.call_count == 2
        assert ReimbursementAccount.query.count() == 0


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_wallet_state_change__error_create_account(
    qualified_alegeus_wallet_hra,
    qualified_wallet_enablement_hra,
):
    """
    Failure to create account record will stop process
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = method + ":" + url

        # get_employee_demographic
        if key == f"GET:{ALEGEUS_WCP_URL}/participant/employee/enrollment/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: None
        # post_employee_services_and_banking
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # post_add_employee_account
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Account/None/123/456":
            assert data["employerId"] == "123"
            assert data["employeeId"] == "456"
            assert data["accountTypeCode"] == "HRA"
            assert data["originalPrefundedAmount"] == 50.0

            mock_response.status_code = 500

        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request, patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search",
        return_value=qualified_wallet_enablement_hra,
    ):
        old_state = WalletState.PENDING

        handle_wallet_state_change(qualified_alegeus_wallet_hra, old_state)

        assert mock_request.call_count == 3
        assert ReimbursementAccount.query.count() == 0


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_wallet_state_change__error_create_dependents(
    qualified_alegeus_wallet_with_dependents,
    qualified_wallet_enablement_hdhp_family,
):
    """
    Failure to create dependents will stop process
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = method + ":" + url

        # get_employee_demographic
        if key == f"GET:{ALEGEUS_WCP_URL}/participant/employee/enrollment/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: None
        # post_employee_services_and_banking
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # get_dependents
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/dependent/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: []
        # post_dependent_services (called once)
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Dependent/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 500

        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search",
        return_value=qualified_wallet_enablement_hdhp_family,
    ):
        old_state = WalletState.PENDING

        handle_wallet_state_change(qualified_alegeus_wallet_with_dependents, old_state)

        assert mock_request.call_count == 4
        assert ReimbursementAccount.query.count() == 0


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_wallet_state_change__error_link_dependents(
    qualified_alegeus_wallet_with_dependents,
    qualified_wallet_enablement_hdhp_family,
    get_employee_accounts_list_response_hdhp_family,
):
    """
    Failure to link dependents will log error, but all other records created
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = method + ":" + url

        # get_employee_demographic
        if key == f"GET:{ALEGEUS_WCP_URL}/participant/employee/enrollment/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: None
        # post_employee_services_and_banking
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # get_dependents
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/dependent/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: []
        # post_dependent_services (called twice)
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Dependent/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # post_add_employee_account
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Account/None/123/456":
            assert data["employerId"] == "123"
            assert data["employeeId"] == "456"
            assert data["accountTypeCode"] == "DTR"
            assert data["originalPrefundedAmount"] == 0
            assert data["coverageTierId"] == "FAMILY"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # get_account_summary
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/accounts/summary/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: get_employee_accounts_list_response_hdhp_family
        # post_link_dependent_to_employee_account (called twice)
        elif (
            key
            == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Account/DependentAccount/None/123/456"
        ):
            assert data["accountTypeCode"] == "DTR"
            assert data["planId"] == "HDHP"

            mock_response.status_code = 500

        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request, patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search",
        return_value=qualified_wallet_enablement_hdhp_family,
    ):
        old_state = WalletState.PENDING

        handle_wallet_state_change(qualified_alegeus_wallet_with_dependents, old_state)

        assert mock_request.call_count == 9
        assert (
            ReimbursementAccount.query.one().reimbursement_wallet_id
            == qualified_alegeus_wallet_with_dependents.id
        )


@patch(
    "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_wallet_state_change__create_alegeus_id_for_oe_rw(
    qualified_alegeus_wallet_hra,
    qualified_wallet_enablement_hra,
    get_employee_accounts_list_response_hra,
):
    """
    A single employee with an HRA that has no current records in Alegeus
    Should create the employee and account records.
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = method + ":" + url

        # get_employee_demographic
        if key == f"GET:{ALEGEUS_WCP_URL}/participant/employee/enrollment/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: None
        # post_employee_services_and_banking
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # post_add_employee_account
        elif key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Account/None/123/456":
            assert data["employerId"] == "123"
            assert data["employeeId"] == "456"
            assert data["accountTypeCode"] == "HRA"
            assert data["originalPrefundedAmount"] == 50.0

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        # get_account_summary
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/accounts/summary/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: get_employee_accounts_list_response_hra

        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ), patch(
        "eligibility.e9y.wallet_enablement_by_org_identity_search",
        return_value=qualified_wallet_enablement_hra,
    ):
        old_state = WalletState.PENDING
        qualified_alegeus_wallet_hra.alegeus_id = None
        handle_wallet_state_change(qualified_alegeus_wallet_hra, old_state)

        assert qualified_alegeus_wallet_hra.alegeus_id is not None


@pytest.mark.parametrize(
    argnames="categories, is_direct_payment_eligible, success_flag, allowed_members, expected_call, "
    "expected_event_name",
    argvalues=[
        # test_1 Unshareable DP Wallet that was configured successfully
        (
            ("fertility", 5000, None),
            True,
            True,
            AllowedMembers.SINGLE_EMPLOYEE_ONLY,
            True,
            "mmb_wallet_qualified_not_shareable",
        ),
        # test_2 Classic Wallet that was configured successfully
        (
            ("other", 3000, None),
            False,
            True,
            AllowedMembers.SINGLE_EMPLOYEE_ONLY,
            True,
            "wallet_state_qualified",
        ),
        # test_3 DP Wallet that was not was configured successfully
        (
            ("fertility", 5000, None),
            True,
            False,
            AllowedMembers.SINGLE_EMPLOYEE_ONLY,
            False,
            None,
        ),
        # test_4 Classic Wallet that was not was configured successfully
        (
            ("other", 3000, None),
            False,
            False,
            AllowedMembers.SINGLE_EMPLOYEE_ONLY,
            False,
            None,
        ),
        # test_5 Shareable DP Wallet that was configured successfully
        (
            ("fertility", 5000, None),
            True,
            True,
            AllowedMembers.SHAREABLE,
            True,
            "mmb_wallet_qualified_not_shareable",
        ),
    ],
    ids=["test_1", "test_2", "test_3", "test_4", "test_5"],
)
def test_category_wallet(
    enterprise_user,
    wallet_for_events,
    categories,
    is_direct_payment_eligible,
    success_flag,
    allowed_members,
    expected_call,
    expected_event_name,
):
    wallet = wallet_for_events(categories, is_direct_payment_eligible, allowed_members)
    old_state = WalletState.PENDING

    with patch(
        "wallet.services.reimbursement_wallet_state_change.use_alegeus_for_reimbursements",
        return_value=True,
    ):
        with patch(
            "wallet.services.reimbursement_wallet_state_change.configure_wallet_in_alegeus",
            return_value=(
                success_flag,
                [FlashMessage("something", FlashMessageCategory.INFO)],
            ),
        ):
            with patch("utils.braze.send_event_by_ids") as mock_send_event_by_ids:
                _ = handle_wallet_state_change(wallet, old_state)
    assert mock_send_event_by_ids.called == expected_call
    if mock_send_event_by_ids.called:
        kwargs = mock_send_event_by_ids.call_args.kwargs
        assert kwargs["event_name"] == expected_event_name
        assert kwargs["user_id"] == enterprise_user.id
        assert kwargs["user_esp_id"] == enterprise_user.esp_id
