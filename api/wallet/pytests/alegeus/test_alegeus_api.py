import datetime
import time
from decimal import Decimal
from unittest import mock
from unittest.mock import DEFAULT, Mock, patch

import jwt
import pytest
import requests
from werkzeug.exceptions import Forbidden

from pytests.freezegun import freeze_time
from wallet.alegeus_api import (
    AlegeusApi,
    format_name_field,
    sanitize_file_name_for_alegeus,
)
from wallet.models.constants import (
    AlegeusCoverageTier,
    ReimbursementRequestExpenseTypes,
    WalletState,
)
from wallet.models.reimbursement import (
    ReimbursementAccount,
    ReimbursementClaim,
    ReimbursementRequest,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import ReimbursementClaimFactory


def test_create_access_token__HTTPError(alegeus_api, logs):
    mock_response = requests.Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}
    error_msg = "AlegeusAPI request failed"
    with patch("common.base_http_client.requests.request", return_value=mock_response):
        alegeus_api.get_access_token()
        log = next((r for r in logs if error_msg in r["event"]), None)
        assert alegeus_api.access_token is None
        assert log is not None


def test_create_access_token__HTTPError_not_json(alegeus_api, logs):
    mock_response = requests.Response()
    mock_response.status_code = 403
    mock_response._content = ""
    error_msg = "AlegeusAPI request failed"
    with patch("common.base_http_client.requests.request", return_value=mock_response):
        alegeus_api.get_access_token()
        log = next((r for r in logs if error_msg in r["event"]), None)
        assert alegeus_api.access_token is None
        assert log is not None


def test_create_access_token__error(alegeus_api, logs):
    error_msg = "AlegeusAPI request failed"
    with patch("common.base_http_client.requests.request", side_effect=Exception()):
        alegeus_api.get_access_token()
        log = next((r for r in logs if error_msg in r["event"]), None)
        assert alegeus_api.access_token is None
        assert log is not None


def test_create_access_token(alegeus_api):
    access_token = "TOKEN"
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {"access_token": access_token}

    with patch("common.base_http_client.requests.request", return_value=mock_response):
        alegeus_api.get_access_token()

        assert alegeus_api.access_token == access_token


def test_get_access_token__reuse_token(alegeus_api):
    now = datetime.datetime.utcnow()
    upcoming_time = now + datetime.timedelta(seconds=2)
    later_time = now + datetime.timedelta(seconds=4)

    access_token_1 = jwt.encode({"exp": upcoming_time}, "secret")
    access_token_2 = jwt.encode({"exp": later_time}, "secret")

    with patch("common.base_http_client.requests.request") as mock_request:
        mock_request.return_value = Mock(
            status_code=200, json=lambda: {"access_token": access_token_1}
        )
        alegeus_api.get_access_token()

        assert alegeus_api.access_token == access_token_1

        with freeze_time(now):
            mock_request.return_value = Mock(
                status_code=200, json=lambda: {"access_token": access_token_2}
            )
            alegeus_api.get_access_token()

            assert alegeus_api.access_token == access_token_1


def test_get_access_token__new_token(alegeus_api):
    now = datetime.datetime.utcnow()
    upcoming_time = now + datetime.timedelta(seconds=2)
    later_time = now + datetime.timedelta(seconds=4)

    access_token_1 = jwt.encode({"exp": upcoming_time}, "secret")
    access_token_2 = jwt.encode({"exp": later_time}, "secret")

    with patch("common.base_http_client.requests.request") as mock_request:
        mock_request.return_value = Mock(
            status_code=200, json=lambda: {"access_token": access_token_1}
        )
        alegeus_api.get_access_token()
        assert alegeus_api.access_token == access_token_1

        with freeze_time(now + datetime.timedelta(seconds=3)):
            mock_request.return_value = Mock(
                status_code=200, json=lambda: {"access_token": access_token_2}
            )
            alegeus_api.get_access_token()

            assert alegeus_api.access_token == access_token_2


def test_make_api_request(alegeus_api):
    access_token = "TOKEN"
    mock_token_response = (access_token, time.time() + 10000)

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch.object(
        AlegeusApi,
        "_create_access_token",
        side_effect=[mock_token_response],
    ):
        alegeus_api.get_access_token()
        assert alegeus_api.access_token == access_token
        with patch(
            "common.base_http_client.requests.request", return_value=mock_response
        ) as mock_request:
            alegeus_api.make_api_request(
                "https://catfact.ninja/fact", api_version="9.0"
            )

            request_headers = mock_request.call_args.kwargs.get("headers")
            assert "Authorization" in request_headers
            assert access_token in request_headers["Authorization"]
            assert request_headers["api-version"] == "9.0"


def test_make_api_request__HTTPError(alegeus_api):
    access_token = "TOKEN"
    mock_token_response = (access_token, time.time() + 10000)

    mock_response = requests.Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    with patch.object(
        AlegeusApi,
        "_create_access_token",
        side_effect=[mock_token_response],
    ):
        alegeus_api.get_access_token()
        assert alegeus_api.access_token == access_token

        with patch(
            "common.base_http_client.requests.request", return_value=mock_response
        ):
            response = alegeus_api.make_api_request("https://catfact.ninja/fact")

            assert response.status_code == 418


def test_make_api_request__retry_on_token_error(alegeus_api):
    """
    Make an alegeus api request that fails with token error, and then retry with a new token
    """

    mock_token_response_1 = ("TOKEN1", time.time() + 10000)
    mock_token_response_2 = ("TOKEN2", time.time() + 10000)

    def make_request_side_effect(
        headers=None,
        **kwargs,
    ):
        if headers.get("Authorization") == "Bearer TOKEN1":
            # First token, will fail
            mock_response = requests.Response()
            mock_response.status_code = 401
            mock_response.url = "http://example.com"
            mock_response.json = lambda: {
                "Code": 401,
                "Description": "invalid token format",
                "Id": -1,
                "Module": "Authentication",
            }
            return mock_response
        else:
            # Second token, will work
            mock_response = requests.Response()
            mock_response.status_code = 200
            return mock_response

    with patch.object(
        AlegeusApi,
        "_create_access_token",
        side_effect=[mock_token_response_1, mock_token_response_2],
    ) as mock_token_request:
        alegeus_api.get_access_token()
        assert alegeus_api.access_token == "TOKEN1"

        with patch(
            "common.base_http_client.requests.request",
            side_effect=make_request_side_effect,
        ) as mock_request:
            response = alegeus_api.make_api_request("https://catfact.ninja/fact")

            # Check success on second token
            assert mock_token_request.call_count == 2
            assert mock_request.call_count == 2
            assert alegeus_api.access_token == "TOKEN2"
            assert response.status_code == 200


def test_make_api_request__retry_only_once_token_error(alegeus_api):
    """
    Make an alegeus api request that fails with token error, and then retry with a new token
    """
    mock_token_response_1 = ("TOKEN1", time.time() + 10000)
    mock_token_response_2 = ("TOKEN2", time.time() + 10000)

    mock_response = requests.Response()
    mock_response.status_code = 401
    mock_response.json = lambda: {
        "Code": 401,
        "Description": "invalid token format",
        "Id": -1,
        "Module": "Authentication",
    }

    with patch.object(
        AlegeusApi,
        "_create_access_token",
        side_effect=[mock_token_response_1, mock_token_response_2],
    ) as mock_token_request:
        alegeus_api.get_access_token()
        assert alegeus_api.access_token == "TOKEN1"

        with patch(
            "common.base_http_client.requests.request", return_value=mock_response
        ) as mock_request:
            response = alegeus_api.make_api_request("https://catfact.ninja/fact")

            # Check failure on second token
            assert response.status_code != 200
            assert alegeus_api.access_token == "TOKEN2"
            assert mock_token_request.call_count == 2
            assert mock_request.call_count == 2


def test_make_api_request__no_token_returned(alegeus_api):
    mock_token_response = (None, None)

    with patch.object(
        AlegeusApi,
        "_create_access_token",
        side_effect=[mock_token_response, mock_token_response],
    ):
        alegeus_api.get_access_token()
        assert alegeus_api.access_token is None

        response = alegeus_api.make_api_request("https://catfact.ninja/fact")

        assert response.status_code == 401


def test_get_employee_activity_times_out_with_exception(
    qualified_alegeus_wallet_hdhp_single, alegeus_api
):
    access_token = "TOKEN"
    mock_token_response = (access_token, time.time() + 10000)

    with patch.object(
        AlegeusApi, "_create_access_token", return_value=mock_token_response
    ):
        alegeus_api.get_access_token()
        assert alegeus_api.access_token == access_token

    with patch("common.base_http_client.requests.request") as mock_request:
        mock_request.side_effect = requests.Timeout()

        response = alegeus_api.get_employee_activity(
            qualified_alegeus_wallet_hdhp_single
        )
        assert response.status_code == 408


def test_make_api_request__error(alegeus_api):
    access_token = "TOKEN"
    mock_token_response = (access_token, time.time() + 10000)

    mock_error = Exception()
    mock_error.response = requests.Response()
    mock_error.response.json = lambda: {}

    with patch.object(
        AlegeusApi, "_create_access_token", return_value=mock_token_response
    ):
        alegeus_api.get_access_token()
        assert alegeus_api.access_token == access_token

    with patch("common.base_http_client.requests.request") as mock_request:
        mock_request().raise_for_status.side_effect = mock_error

        response = alegeus_api.make_api_request("https://catfact.ninja/fact")

        assert response.status_code == 400


def test_get_employee_demographic(qualified_alegeus_wallet_hdhp_single, alegeus_api):
    """
    Tests that a User / Employee has been created in Alegeus.
    """
    response_body = {
        "AddressLine1": "160 Varick St",
        "AddressLine2": "6th Floor",
        "BirthDate": "",
        "City": "New York",
        "Country": "US",
        "DriverLicenceNumber": "",
        "Email": "test+fert.444330@mavenclinic.com",
        "EmployeeSSN": "",
        "FirstName": "John5894",
        "Gender": 0,
        "LastName": "Baker",
        "LastUpdated": "/Date(1632414387023-0500)/",
        "MaritalStatus": 0,
        "MiddleInitial": "N",
        "MiscData": {
            "BaseSalary": 0,
            "CitizenStatusCode": -1,
            "CitizenshipCountry": "",
            "EmployerCity": "",
            "EmployerName": "",
            "EmployerState": "",
            "EmployermentStatus": -1,
            "JobTitle": "",
        },
        "MotherMaidenName": "",
        "ParticipantId": "T1hsHslyYzJ5tE3fHCW2jtphnbnI0Qb3JSZtTQpWMcY=",
        "Phone": "",
        "ShippingAddressCity": "",
        "ShippingAddressCountry": "",
        "ShippingAddressLine1": "",
        "ShippingAddressLine2": "",
        "ShippingAddressState": "",
        "ShippingAddressZip": "",
        "State": "NY",
        "Zip": "10013",
    }

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda x: response_body

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.get_employee_demographic(
            wallet=qualified_alegeus_wallet_hdhp_single
        )

        assert response.status_code == 200


def test_get_account_summary(qualified_alegeus_wallet_hdhp_single, alegeus_api):
    """
    Tests that GET request contains the required information to update the Reimbursement Account.
    - flex account key, plan, account type
    """
    response_body = [
        {
            "AccountType": "HRA",
            "AcctStatusCde": 2,
            "AcctTypeClassDescription": "HRA",
            "AvailBalance": 99907900.0000,
            "Balance": 99907900.0000,
            "ExternalFunded": None,
            "FlexAccountKey": 17,
            "HSABalance": 99907900.0000,
            "HraAcct": False,
            "IsWCABank": None,
            "Payments": 92100.0000,
            "PlanEndDate": "21991231",
            "PlanId": "FERTHRA2021",
            "PlanOptions2": 2,
            "PlanStartDate": "20210101",
            "PlanYear": 1,
        }
    ]

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda x: response_body

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.get_account_summary(
            wallet=qualified_alegeus_wallet_hdhp_single
        )

        assert response.status_code == 200


def test_put_employee_services_and_banking(
    qualified_alegeus_wallet_hdhp_single, alegeus_api
):
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda x: {}

    today = datetime.datetime(2022, 10, 6)

    banking_info = {
        "BankAcctName": "Test Checking",
        "BankAccount": "0037308343",
        "BankAccountTypeCode": "1",
        "BankRoutingNumber": "064000017",
    }

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request"
    ) as mock_request, patch.object(
        ReimbursementWallet, "get_first_name_last_name_and_dob"
    ) as get_first_name_last_name_and_dob_mock:
        mock_request.return_value = mock_response
        get_first_name_last_name_and_dob_mock.return_value = [
            "Sarah Jane",
            "Smith",
            datetime.datetime(2000, 5, 17),
        ]

        response = alegeus_api.put_employee_services_and_banking(
            qualified_alegeus_wallet_hdhp_single, banking_info, termination_date=today
        )

        assert response.status_code == 200
        assert mock_request.call_args.kwargs["data"]["FirstName"] == "Sarah Jane"
        assert mock_request.call_args.kwargs["data"]["LastName"] == "Smith"
        assert (
            mock_request.call_args.kwargs["data"]["TerminationDate"]
            == today.isoformat()
        )


def test_put_employee_services_and_banking__invalid_banking_info(
    qualified_alegeus_wallet_hdhp_single, alegeus_api
):
    invalid_key = "INVALID"
    banking_info = {
        "BankAcctName": "Test Checking",
        "BankAccount": "0037308343",
        "BankAccountTypeCode": "1",
        invalid_key: "064000017",
    }

    with pytest.raises(
        AssertionError, match=f"{invalid_key} is not a valid banking info field. .*"
    ):
        alegeus_api.put_employee_services_and_banking(
            qualified_alegeus_wallet_hdhp_single, banking_info
        )


def test_post_employee_services_and_banking(
    qualified_alegeus_wallet_hdhp_single, alegeus_api
):
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request"
    ) as mock_request, patch.object(
        ReimbursementWallet, "get_first_name_last_name_and_dob"
    ) as get_first_name_last_name_and_dob_mock:
        mock_request.return_value = mock_response
        get_first_name_last_name_and_dob_mock.return_value = [
            "Miss",
            "Maven",
            datetime.datetime(2000, 5, 17),
        ]

        response = alegeus_api.post_employee_services_and_banking(
            qualified_alegeus_wallet_hdhp_single
        )

        assert response.status_code == 200


def test_post_employee_services_and_banking__employee_already_exists(
    qualified_alegeus_wallet_hdhp_single, alegeus_api
):
    mock_response = requests.Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request"
    ) as mock_request, patch.object(
        ReimbursementWallet, "get_first_name_last_name_and_dob"
    ) as get_first_name_last_name_and_dob_mock:
        mock_request.return_value = mock_response
        get_first_name_last_name_and_dob_mock.return_value = [
            "Miss",
            "Maven",
            datetime.datetime(2000, 5, 17),
        ]

        response = alegeus_api.post_employee_services_and_banking(
            qualified_alegeus_wallet_hdhp_single
        )

        assert response.status_code == 418


def test_post_dependent_services(
    qualified_alegeus_wallet_hdhp_single, factories, alegeus_api
):
    dependent = factories.OrganizationEmployeeDependentFactory.create(
        alegeus_dependent_id="abc123",
        reimbursement_wallet=qualified_alegeus_wallet_hdhp_single,
    )

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}
    first_name = getattr(dependent, "first_name", "")
    last_name = getattr(dependent, "last_name", "")

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.post_dependent_services(
            qualified_alegeus_wallet_hdhp_single,
            dependent.alegeus_dependent_id,
            first_name,
            last_name,
        )

        assert response.status_code == 200


def test_post_dependent_services__invalid_dependent_info(
    qualified_alegeus_wallet_hdhp_single, factories, alegeus_api
):
    dependent = factories.OrganizationEmployeeDependentFactory.create(
        reimbursement_wallet=qualified_alegeus_wallet_hdhp_single,
        alegeus_dependent_id="abc123",
    )

    mock_response = requests.Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}
    first_name = getattr(dependent, "first_name", "")
    last_name = getattr(dependent, "last_name", "")
    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.post_dependent_services(
            qualified_alegeus_wallet_hdhp_single,
            dependent.alegeus_dependent_id,
            first_name,
            last_name,
        )

        assert response.status_code == 418


def test_post_link_dependent_to_employee_account(
    qualified_alegeus_wallet_hdhp_single,
    valid_alegeus_plan_hdhp,
    factories,
    alegeus_api,
):
    dependent = factories.OrganizationEmployeeDependentFactory.create(
        reimbursement_wallet=qualified_alegeus_wallet_hdhp_single,
        alegeus_dependent_id="abc123",
    )

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.post_link_dependent_to_employee_account(
            qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp, dependent
        )

        assert response.status_code == 200


def test_post_link_dependent_to_employee_account__invalid_request(
    qualified_alegeus_wallet_hdhp_single,
    valid_alegeus_plan_hdhp,
    factories,
    alegeus_api,
):
    dependent = factories.OrganizationEmployeeDependentFactory.create(
        reimbursement_wallet=qualified_alegeus_wallet_hdhp_single,
        alegeus_dependent_id="abc123",
    )

    mock_response = requests.Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.post_link_dependent_to_employee_account(
            qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp, dependent
        )

        assert response.status_code == 418


def test_post_add_employee_account(
    qualified_alegeus_wallet_hdhp_single,
    valid_alegeus_plan_hdhp,
    alegeus_api,
):
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    def mock_api_request_side_effect(url, data=None, **kwargs):
        assert data["originalPrefundedAmount"] == 1.0
        return DEFAULT

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response
        mock_request.side_effect = mock_api_request_side_effect

        response = alegeus_api.post_add_employee_account(
            wallet=qualified_alegeus_wallet_hdhp_single,
            plan=valid_alegeus_plan_hdhp,
            prefunded_amount=100,
            start_date=datetime.date.today(),
            coverage_tier=None,
        )

        assert response.status_code == 200


def test_post_add_employee_account_hdhp_single(
    qualified_alegeus_wallet_hdhp_single,
    valid_alegeus_plan_hdhp,
    alegeus_api,
):
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    def mock_api_request_side_effect(url, data=None, **kwargs):
        assert data["coverageTierId"] == "SINGLE"
        return DEFAULT

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response
        mock_request.side_effect = mock_api_request_side_effect

        response = alegeus_api.post_add_employee_account(
            wallet=qualified_alegeus_wallet_hdhp_single,
            plan=valid_alegeus_plan_hdhp,
            prefunded_amount=100,
            start_date=datetime.date.today(),
            coverage_tier=AlegeusCoverageTier.SINGLE,
        )

        assert response.status_code == 200


def test_post_add_employee_account_hdhp_family(
    qualified_alegeus_wallet_hdhp_single,
    valid_alegeus_plan_hdhp,
    alegeus_api,
):
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    def mock_api_request_side_effect(url, data=None, **kwargs):
        assert data["coverageTierId"] == "FAMILY"
        return DEFAULT

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response
        mock_request.side_effect = mock_api_request_side_effect

        response = alegeus_api.post_add_employee_account(
            wallet=qualified_alegeus_wallet_hdhp_single,
            plan=valid_alegeus_plan_hdhp,
            prefunded_amount=100,
            start_date=datetime.date.today(),
            coverage_tier=AlegeusCoverageTier.FAMILY,
        )

        assert response.status_code == 200


def test_post_add_employee_account__invalid_request(
    qualified_alegeus_wallet_hdhp_single,
    valid_alegeus_plan_hdhp,
    alegeus_api,
):
    mock_response = requests.Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.post_add_employee_account(
            wallet=qualified_alegeus_wallet_hdhp_single,
            plan=valid_alegeus_plan_hdhp,
            prefunded_amount=100,
            start_date=datetime.date.today(),
            coverage_tier=None,
        )

        assert response.status_code == 418


def test_post_add_qle__success(
    qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp, alegeus_api
):
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.post_add_qle(
            qualified_alegeus_wallet_hdhp_single,
            valid_alegeus_plan_hdhp,
            100,
            datetime.datetime.utcnow(),
        )

        assert response.status_code == 200


def test_post_add_qle__invalid_request(
    qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp, alegeus_api
):
    mock_response = requests.Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.post_add_qle(
            qualified_alegeus_wallet_hdhp_single,
            valid_alegeus_plan_hdhp,
            100,
            datetime.datetime.utcnow(),
        )

        assert response.status_code == 418


def test_get_employee_activity(qualified_alegeus_wallet_hdhp_single, alegeus_api):
    """
    Tests retrieving Claims that have either been approved or denied.
    """
    response_body = [
        {
            "Amount": 600.0000,
            "Description": "TEST PROVIDER",
            "DisplayStatus": "Approved",
            "ReimbursementMethod": "Payroll",
            "SettlementDate": "20211103",
            "Status": "Approved",
            "StatusCode": 2,
            "TrackingNumber": "86DF0759DA9AA09A427C",
            "Type": "MANUAL CLAIM",
            "CustomDescription": "Health Reimbursement",
            "AcctTypeCode": "HRA",
            "FlexAcctKey": 17,
        }
    ]

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda x: response_body

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.get_employee_activity(
            wallet=qualified_alegeus_wallet_hdhp_single
        )

        assert response.status_code == 200


def test_get_transaction_details(qualified_alegeus_wallet_hdhp_single, alegeus_api):
    """
    Tests retrieving Transactions Details
    """
    response_body = {
        "Amount": 100.0000,
        "Notes": "Prepaid",
        "SettlementDate": "20221024",
        "SettlementSeqNum": 30000005,
        "TransactionKey": "1130000005-20221024-12145460",
        "TransactionStatus": 7,
    }

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda x: response_body

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request"
    ) as mock_make_api_request:
        mock_make_api_request.return_value = mock_response

        response = alegeus_api.get_transaction_details(
            wallet=qualified_alegeus_wallet_hdhp_single,
            transactionid=response_body.get("TransactionKey"),
            seqnum=response_body.get("SettlementSeqNum"),
            setldate=response_body.get("SettlementDate"),
        )

        assert response.status_code == 200
        assert response.json == mock_response.json


def test_post_claim(
    wallet_with_pending_requests_with_claims_and_attachments,
    alegeus_api,
):
    """
    Tests successful POST call to submit Claims that are Pending
    """
    reimbursement_request = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_requests[
            0
        ]
    )

    reimbursement_account = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_accounts[
            0
        ]
    )

    reimbursement_claim = reimbursement_request.claims[0]

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.post_claim(
            wallet=wallet_with_pending_requests_with_claims_and_attachments,
            reimbursement_request=reimbursement_request,
            reimbursement_account=reimbursement_account,
            reimbursement_claim=reimbursement_claim,
        )

        assert response.status_code == 200


def test_post_claim__with_scc_code(
    wallet_with_pending_requests_with_claims_and_attachments,
    alegeus_api,
    expense_subtypes,
):
    reimbursement_request = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_requests[
            0
        ]
    )

    # eventually move these settings up to be used by more tests
    reimbursement_request.expense_type = ReimbursementRequestExpenseTypes.FERTILITY
    reimbursement_request.wallet_expense_subtype = expense_subtypes["FIVF"]

    reimbursement_account = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_accounts[
            0
        ]
    )

    reimbursement_claim = reimbursement_request.claims[0]

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.post_claim(
            wallet=wallet_with_pending_requests_with_claims_and_attachments,
            reimbursement_request=reimbursement_request,
            reimbursement_account=reimbursement_account,
            reimbursement_claim=reimbursement_claim,
        )

        assert response.status_code == 200
        data = mock_request.call_args.kwargs["data"]
        assert data["Claims"][0]["ScCde"] == "FIVF"
        assert "FlexAcctKey" not in data["Claims"][0]


@pytest.mark.parametrize(
    argnames=(
        "wallet_with_pending_currency_specific_request_no_claims",
        "expected_amount",
    ),
    argvalues=[
        ((10000, None, None), Decimal("100.00")),
        ((10000, None, "USD"), Decimal("100.00")),
        ((None, 20000, "AUD"), Decimal("200.00")),
        ((None, 30000, "NZD"), Decimal("300.00")),
    ],
    ids=[
        "USD-request-where-benefit-currency-is-None",
        "USD-request-where-benefit-currency-is-USD",
        "AUD-request-where-benefit-currency-is-AUD",
        "NZD-request-where-benefit-currency-is-NZD",
    ],
    indirect=["wallet_with_pending_currency_specific_request_no_claims"],
)
def test_post_claim_submits_correct_amount(
    alegeus_api,
    wallet_with_pending_currency_specific_request_no_claims: ReimbursementWallet,
    expected_amount: int,
):
    """
    Tests successful POST call with correct amount to submit Claims that are Pending
    """
    # Given
    reimbursement_request: ReimbursementRequest = (
        wallet_with_pending_currency_specific_request_no_claims.reimbursement_requests[
            0
        ]
    )
    reimbursement_account: ReimbursementAccount = (
        wallet_with_pending_currency_specific_request_no_claims.reimbursement_accounts[
            0
        ]
    )
    reimbursement_claim: ReimbursementClaim = ReimbursementClaimFactory.create(
        alegeus_claim_id="123abc",
        alegeus_claim_key=1,
        status="pending",
        reimbursement_request=reimbursement_request,
        amount=expected_amount,
    )

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: {}
        mock_request.return_value = mock_response

        # When
        _ = alegeus_api.post_claim(
            wallet=wallet_with_pending_currency_specific_request_no_claims,
            reimbursement_request=reimbursement_request,
            reimbursement_account=reimbursement_account,
            reimbursement_claim=reimbursement_claim,
        )

    # Then
    mock_request.assert_called_with(
        mock.ANY,
        api_version=mock.ANY,
        data={
            "Claims": [
                {
                    "Claimant": {},
                    "ServiceStartDate": mock.ANY,
                    # Main assertion of this test, make sure the amount is correct
                    "TxnAmt": expected_amount,
                    "TrackingNum": mock.ANY,
                }
            ]
        },
        method="POST",
    )


def test_post_claim__invalid_request(
    wallet_with_pending_requests_with_claims_and_attachments,
    alegeus_api,
):
    reimbursement_request = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_requests[
            0
        ]
    )

    reimbursement_account = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_accounts[
            0
        ]
    )

    reimbursement_claim = reimbursement_request.claims[0]

    mock_response = requests.Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.post_claim(
            wallet=wallet_with_pending_requests_with_claims_and_attachments,
            reimbursement_request=reimbursement_request,
            reimbursement_account=reimbursement_account,
            reimbursement_claim=reimbursement_claim,
        )

        assert response.status_code == 418


def test_upload_attachment_for_claim(
    qualified_alegeus_wallet_hdhp_single, enterprise_user_asset, alegeus_api
):
    claim_key = 1
    attachment_b64_str = "base64string"

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.upload_attachment_for_claim(
            qualified_alegeus_wallet_hdhp_single,
            enterprise_user_asset,
            claim_key,
            attachment_b64_str,
        )

        assert response.status_code == 200


def test_upload_attachment_for_claim__invalid_request(
    qualified_alegeus_wallet_hdhp_single, enterprise_user_asset, alegeus_api
):
    claim_key = 1
    attachment_b64_str = "base64string"

    mock_response = requests.Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.upload_attachment_for_claim(
            qualified_alegeus_wallet_hdhp_single,
            enterprise_user_asset,
            claim_key,
            attachment_b64_str,
        )

        assert response.status_code == 418


def test_upload_attachment_for_claim__bad_file_name(
    qualified_alegeus_wallet_hdhp_single, enterprise_user_asset, alegeus_api
):
    claim_key = 1
    attachment_b64_str = "base64string"

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    enterprise_user_asset.file_name = "test -:*<>?| bad file_name:-_"

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.upload_attachment_for_claim(
            qualified_alegeus_wallet_hdhp_single,
            enterprise_user_asset,
            claim_key,
            attachment_b64_str,
        )

        assert response.status_code == 200


@pytest.mark.parametrize(
    "input_name,expected_name",
    [
        ("", ""),  # no-op
        ("Jane", "Jane"),  # only English letters
        ("O'Toole", "O'Toole"),  # apostrophe preserved
        ("Mary Jane", "Mary Jane"),  # space preserved
        ("Mary-Jane", "Mary-Jane"),  # hyphen preserved
        ("Jones, Sr.", "Jones, Sr."),  # suffix preserved
        ("José", "Jose"),  # accent removed
        ("Zoë", "Zoe"),  # umlaut removed
        ("Ållïsón", "Allison"),  # multiple characters
        ("Þorbjörn", "orbjorn"),  # un-transliteratable character
        ("ß", "---"),  # all characters un-transliteratable
    ],
)
def test__format_name_field(input_name: str, expected_name: str):
    result = format_name_field(input_name)
    assert result == expected_name


@pytest.mark.parametrize(
    "input_file_name,expected_file_name",
    [
        ("", ".jpg"),
        ("Test1", "Test1.jpg"),
        ("test : 1", "test_-_1.jpg"),
        ("test :_ 1", "test_-__1.jpg"),
        ("test*<>?| 1", "test_1.jpg"),
        ("test*<:? 1", "test-_1.jpg"),
    ],
)
def test__sanitize_file_name_for_alegeus(input_file_name: str, expected_file_name: str):
    content_type = "image/jpeg"
    result = sanitize_file_name_for_alegeus(input_file_name, content_type)
    assert result == expected_file_name


def test_request_submits_with_runout_wallet_state(
    alegeus_api, qualified_alegeus_wallet_hdhp_single
):
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = {}
    qualified_alegeus_wallet_hdhp_single.state = WalletState.RUNOUT
    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        response = alegeus_api.get_employee_demographic(
            wallet=qualified_alegeus_wallet_hdhp_single
        )

        assert response.status_code == 200


def test_request_fails_with_pending_state(
    alegeus_api, qualified_alegeus_wallet_hdhp_single
):
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = {}
    qualified_alegeus_wallet_hdhp_single.state = WalletState.PENDING
    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response
        with pytest.raises(Forbidden):
            response = alegeus_api.get_employee_demographic(
                wallet=qualified_alegeus_wallet_hdhp_single
            )
            assert response.status_code == 403
