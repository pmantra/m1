import datetime
from unittest.mock import patch

import requests

from pytests import factories
from wallet.alegeus_api import ALEGEUS_WCA_URL
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.tasks.alegeus import (
    update_member_demographics,
    update_or_create_dependent_demographics,
)


@patch(
    "wallet.tasks.alegeus.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_update_member_demographic__success(
    qualified_alegeus_wallet_hra, qualified_wallet_enablement_hra
):
    """
    Tests that update_member_demographic successfully calls to the Alegeus API
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

        if key == f"GET:{ALEGEUS_WCA_URL}/Services/Employee/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # pretend no bank info

        if key == f"PUT:{ALEGEUS_WCA_URL}/Services/Employee/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored

        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request, patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search",
        return_value=qualified_wallet_enablement_hra,
    ):
        with patch.object(
            ReimbursementWallet, "get_first_name_last_name_and_dob"
        ) as get_first_name_last_name_and_dob_mock:
            get_first_name_last_name_and_dob_mock.return_value = [
                "Winnie",
                "the Pooh",
                datetime.datetime(2000, 5, 17),
            ]
            wallet = qualified_alegeus_wallet_hra
            user_id = wallet.employee_member.id
            update_member_demographics(wallet.id, user_id)
    assert mock_request.call_count == 2


@patch(
    "wallet.tasks.alegeus.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_update_member_demographic__failure():
    """
    Tests that update_member_demographic does not call to the Alegeus API if there is not a wallet.
    """
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}  # response body is ignored

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        return_value=mock_response,
    ) as mock_request:
        # Random wallet_id and user_id that don't exist
        update_member_demographics(999, 3423)

    assert mock_request.call_count == 0


@patch(
    "wallet.tasks.alegeus.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_update_or_create_dependent_demographic__success(
    qualified_alegeus_wallet_hdhp_single,
):
    """
    Tests that update_dependent_demographic successfully calls to the Alegeus API with a wallet and dependent.
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
        if key == f"PUT:{ALEGEUS_WCA_URL}/Services/Employee/Dependent/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request:
        wallet = qualified_alegeus_wallet_hdhp_single
        dependent = factories.OrganizationEmployeeDependentFactory.create(
            alegeus_dependent_id="abc123",
            reimbursement_wallet_id=wallet.id,
        )
        update_or_create_dependent_demographics(wallet.id, dependent.id, False)

    assert mock_request.call_count == 1


@patch(
    "wallet.tasks.alegeus.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_update_or_create_dependent_demographic_invalid_dependent__failure(
    qualified_alegeus_wallet_hdhp_single,
):
    """
    Tests that update_dependent_demographic does not call to the Alegeus API if there is not a wallet or dependent.
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
        if key == f"PUT:{ALEGEUS_WCA_URL}/Services/Employee/Dependent/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request:
        wallet = qualified_alegeus_wallet_hdhp_single
        update_or_create_dependent_demographics(
            wallet.id, 334, False
        )  # bad dependent id

    assert mock_request.call_count == 0


@patch(
    "wallet.tasks.alegeus.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_update_or_create_dependent_demographic_invalid_wallet_id__failure(
    qualified_alegeus_wallet_hdhp_single,
    qualified_alegeus_wallet_hdhp_family,
):
    """
    Tests that update_dependent_demographic does not call to the Alegeus API if there is not a wallet or dependent.
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
        if key == f"PUT:{ALEGEUS_WCA_URL}/Services/Employee/Dependent/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request:
        wallet = qualified_alegeus_wallet_hdhp_single
        wrong_wallet_id = qualified_alegeus_wallet_hdhp_family.id
        dependent = factories.OrganizationEmployeeDependentFactory.create(
            alegeus_dependent_id="abc123",
            reimbursement_wallet_id=wrong_wallet_id,
        )
        update_or_create_dependent_demographics(wallet.id, dependent.id, False)

    assert mock_request.call_count == 0


@patch(
    "wallet.tasks.alegeus.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_update_or_create_dependent_demographic_create__success(
    qualified_alegeus_wallet_hdhp_single,
):
    """
    Tests that update_dependent_demographic successfully calls to the Alegeus API with a wallet and dependent.
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
        if key == f"POST:{ALEGEUS_WCA_URL}/Services/Employee/Dependent/None/123/456":
            assert data["EmployerId"] == "123"
            assert data["EmployeeId"] == "456"

            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored
        return mock_response

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_request:
        wallet = qualified_alegeus_wallet_hdhp_single
        dependent = factories.OrganizationEmployeeDependentFactory.create(
            alegeus_dependent_id="abc123",
            reimbursement_wallet_id=wallet.id,
        )
        update_or_create_dependent_demographics(wallet.id, dependent.id, True)

    assert mock_request.call_count == 1
