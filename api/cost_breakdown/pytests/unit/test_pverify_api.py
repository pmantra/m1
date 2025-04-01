import json
import os
from datetime import date, datetime
from unittest import mock
from unittest.mock import patch

import pytest
import requests

from cost_breakdown.constants import (
    ELIGIBILITY_SUMMARY_ENDPOINT_NAME,
    MAVEN_PROVIDER_LASTNAME,
    MAVEN_PROVIDER_NPI,
    PVERIFY_CLIENT_API_ID,
    PVERIFY_CLIENT_API_SECRET,
    PVERIFY_URL,
    TOKEN_ENDPOINT_NAME,
    PverifyKeys,
    PverifyPracticeCodes,
)
from cost_breakdown.errors import (
    NoPatientNameFoundError,
    NoRTEPayerFound,
    PverifyEligibilityInfoParsingError,
    PverifyHttpCallError,
    PverifyPlanInactiveError,
    PverifyProcessFailedError,
)
from cost_breakdown.models.rte import RTETransaction
from cost_breakdown.rte.pverify_api import PverifyAPI, get_pverify_key
from pytests.freezegun import freeze_time
from wallet.models.constants import CostSharingCategory


@pytest.fixture(scope="function")
def pverify_api():
    return PverifyAPI()


@pytest.fixture(scope="function")
def pverify_request():
    return {
        "payerCode": "00001",
        "provider": {
            "lastName": MAVEN_PROVIDER_LASTNAME,
            "npi": MAVEN_PROVIDER_NPI,
        },
        "doS_StartDate": "01/01/2023",
        "doS_EndDate": "01/01/2023",
        "PracticeTypeCode": "18",
        "isSubscriberPatient": "True",
        "subscriber": {
            "memberID": "abcdefg",
            "firstName": "alice",
            "lastName": "paul",
            "dob": "01/01/2000",
        },
    }


@pytest.fixture(scope="function")
def pverify_sample_success_response():
    with open(
        os.path.join(
            os.path.dirname(__file__), "../pverify/pverify_sample_success_response.json"
        )
    ) as f:
        data = json.load(f)
    return data


@pytest.fixture(scope="function")
def pverify_sample_tier2_response():
    with open(
        os.path.join(
            os.path.dirname(__file__), "../pverify/pverify_sample_tier2_response.json"
        )
    ) as f:
        data = json.load(f)
    return data


@pytest.fixture(scope="function")
def pverify_sample_failure_response():
    with open(
        os.path.join(
            os.path.dirname(__file__), "../pverify/pverify_sample_failure_response.json"
        )
    ) as f:
        data = json.load(f)
    return data


@pytest.fixture(scope="function")
def pverify_sample_success_no_deductible_response():
    with open(
        os.path.join(
            os.path.dirname(__file__),
            "../pverify/pverify_sample_success_no_deductible_response.json",
        )
    ) as f:
        data = json.load(f)
    return data


@pytest.fixture(scope="function")
def pverify_sample_tier2_response_message(pverify_sample_tier2_response):
    response = requests.Response()
    response.status_code = 200
    response.json = lambda: pverify_sample_tier2_response
    return response


@pytest.fixture(scope="function")
def pverify_response_with_error_message(pverify_sample_failure_response):
    response = requests.Response()
    response.status_code = 200
    response.json = lambda: pverify_sample_failure_response
    return response


@pytest.fixture(scope="function")
def pverify_response_with_inactive_plan(pverify_sample_success_response):
    response = requests.Response()
    response.status_code = 200
    pverify_sample_success_response["PlanCoverageSummary"] = {"Status": "Inactive"}
    response.json = lambda: pverify_sample_success_response
    return response


@pytest.fixture(scope="function")
def pverify_response(pverify_sample_success_response):
    response = requests.Response()
    response.status_code = 200
    response.json = lambda: pverify_sample_success_response
    return response


@pytest.fixture(scope="function")
def pverify_no_deductible_response(pverify_sample_success_no_deductible_response):
    response = requests.Response()
    response.status_code = 200
    response.json = lambda: pverify_sample_success_no_deductible_response
    return response


@pytest.fixture(scope="function")
def pverify_response_empty_fields(pverify_sample_success_response):
    response = requests.Response()
    response.status_code = 200
    hbpc_summary = pverify_sample_success_response["HBPC_Deductible_OOP_Summary"]
    for k in (
        "IndividualDeductibleRemainingInNet",
        "IndividualDeductibleRemainingOutNet",
        "FamilyDeductibleRemainingInNet",
        "FamilyDeductibleRemainingOutNet",
        "IndividualOOPRemainingInNet",
        "IndividualOOPRemainingOutNet",
        "FamilyOOPRemainingInNet",
        "FamilyOOPRemainingOutNet",
    ):
        hbpc_summary[k] = None
    response.json = lambda: pverify_sample_success_response
    return response


def test_make_api_request(pverify_api):
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch(
        "common.base_http_client.requests.request", return_value=mock_response
    ) as mock_request, patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.create_access_token"
    ):
        response = pverify_api.make_api_request(
            ELIGIBILITY_SUMMARY_ENDPOINT_NAME,
            data={"test": "data"},
            method="POST",
            timeout=30,
        )
        kwargs = mock_request.call_args.kwargs

        request_headers = kwargs["headers"]
        assert request_headers["Content-Type"] == "application/json"
        assert "Authorization" in request_headers
        assert "Client-API-Id" in request_headers

        assert kwargs["method"] == "POST"
        assert kwargs["url"] == f"{PVERIFY_URL}{ELIGIBILITY_SUMMARY_ENDPOINT_NAME}"
        assert kwargs["data"] == '{"test": "data"}'
        assert kwargs["params"] == None
        assert kwargs["timeout"] == 30
        assert response == mock_response


def test_make_api_request_http_error(pverify_api):
    mock_error = requests.HTTPError()
    mock_error.response = requests.Response()
    mock_error.response.status_code = 418
    mock_error.response.json = lambda: {}

    with patch("common.base_http_client.requests.request") as mock_request, patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.create_access_token"
    ):
        mock_request().raise_for_status.side_effect = mock_error
        mock_request.call_count = 0
        response = pverify_api.make_api_request(
            ELIGIBILITY_SUMMARY_ENDPOINT_NAME,
            data={"test": "data"},
            method="POST",
            timeout=30,
        )
        assert mock_request.call_count == 1
        assert response.status_code == 418


def test_make_api_request_timeout(pverify_api):
    mock_timeout = requests.Timeout()
    mock_timeout.response = requests.Response()
    mock_timeout.response.status_code = 408
    mock_timeout.response.json = lambda: {}

    with patch("common.base_http_client.requests.request") as mock_request, patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.create_access_token"
    ):
        mock_request().raise_for_status.side_effect = mock_timeout
        mock_request.call_count = 0
        response = pverify_api.make_api_request(
            ELIGIBILITY_SUMMARY_ENDPOINT_NAME,
            data={"test": "data"},
            method="POST",
            timeout=30,
        )
        assert mock_request.call_count == 2
        assert response.status_code == 408


def test_make_api_request_authentication_failure(pverify_api):
    mock_failure = requests.HTTPError()
    mock_failure.response = requests.Response()
    mock_failure.response.status_code = 401
    mock_failure.response.json = lambda: {}

    with patch("common.base_http_client.requests.request") as mock_request, patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.create_access_token"
    ):
        mock_request().raise_for_status.side_effect = mock_failure
        mock_request.call_count = 0
        response = pverify_api.make_api_request(
            ELIGIBILITY_SUMMARY_ENDPOINT_NAME,
            data={"test": "data"},
            method="POST",
            timeout=30,
        )
        assert mock_request.call_count == 2
        assert response.status_code == 401


def test_make_api_request_exception(pverify_api):
    mock_exception = requests.RequestException()
    mock_exception.response = requests.Response()
    mock_exception.response.status_code = 400
    mock_exception.response.json = lambda: {}

    with patch("common.base_http_client.requests.request") as mock_request, patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.create_access_token"
    ):
        mock_request().raise_for_status.side_effect = mock_exception
        mock_request.call_count = 0
        response = pverify_api.make_api_request(
            ELIGIBILITY_SUMMARY_ENDPOINT_NAME,
            data={"test": "data"},
            method="POST",
            timeout=30,
        )
        assert mock_request.call_count == 1
        assert response.status_code == 400


@freeze_time("2023-01-01")
def test_get_eligibility_summary_request_body(pverify_api, member_health_plan_no_name):
    body = pverify_api._get_eligibility_summary_request_body(
        member_health_plan_no_name,
        CostSharingCategory.DIAGNOSTIC_MEDICAL,
        "fiona",
        "fee",
        service_start_date=date(year=2023, month=1, day=1),
    )
    assert body == {
        "payerCode": "00001",
        "provider": {
            "lastName": MAVEN_PROVIDER_LASTNAME,
            "npi": MAVEN_PROVIDER_NPI,
        },
        "doS_StartDate": "01/01/2023",
        "doS_EndDate": "01/01/2023",
        "PracticeTypeCode": "113",
        "isSubscriberPatient": "True",
        "subscriber": {
            "memberID": "abcdefg",
            "firstName": "fiona",
            "lastName": "fee",
            "dob": "01/01/2000",
        },
    }


@freeze_time("2023-01-01")
def test_get_eligibility_summary_request_body_dependent(
    pverify_api, member_health_plan_dependent
):
    body = pverify_api._get_eligibility_summary_request_body(
        member_health_plan_dependent,
        CostSharingCategory.DIAGNOSTIC_MEDICAL,
        "fiona",
        "fee",
        service_start_date=date(year=2023, month=1, day=1),
    )
    assert body == {
        "payerCode": "00001",
        "provider": {
            "lastName": MAVEN_PROVIDER_LASTNAME,
            "npi": MAVEN_PROVIDER_NPI,
        },
        "doS_StartDate": "01/01/2023",
        "doS_EndDate": "01/01/2023",
        "PracticeTypeCode": "113",
        "isSubscriberPatient": "True",
        "subscriber": {
            "memberID": "abcdefg",
            "firstName": "fiona",
            "lastName": "fee",
            "dob": "01/01/2010",
        },
    }


def test_get_eligibility_summary_request_body_no_payer(
    pverify_api, member_health_plan_no_name
):
    member_health_plan_no_name.employer_health_plan.benefits_payer_id = None
    with pytest.raises(NoRTEPayerFound):
        pverify_api._get_eligibility_summary_request_body(
            member_health_plan_no_name,
            CostSharingCategory.DIAGNOSTIC_MEDICAL,
            "fiona",
            "fee",
            service_start_date=date(year=2023, month=1, day=1),
        )


class TestHandleEligibilitySummaryResponse:
    @pytest.mark.parametrize(
        argnames="status_code,error_message",
        argvalues=[
            (408, "timeout"),
            (401, "Authentication failure"),
            (400, "request failure"),
            (500, "server internal error"),
        ],
    )
    def test_request_exception(
        self,
        status_code,
        error_message,
        pverify_api,
        member_health_plan,
        pverify_request,
    ):
        mock_response = requests.Response()
        mock_response.status_code = status_code
        mock_response.json = lambda: error_message

        with pytest.raises(PverifyHttpCallError):
            pverify_api._handle_eligibility_summary_response(
                member_health_plan,
                pverify_request,
                mock_response,
                CostSharingCategory.CONSULTATION,
            )

        rte_transaction = RTETransaction.query.filter(
            RTETransaction.member_health_plan_id == member_health_plan.id
        ).one()
        assert rte_transaction.response_code == status_code
        assert rte_transaction.request == pverify_request
        assert rte_transaction.error_message == error_message

    def test_pverify_error_message_returned(
        self,
        member_health_plan,
        pverify_api,
        pverify_request,
        pverify_response_with_error_message,
    ):
        with pytest.raises(PverifyProcessFailedError):
            pverify_api._handle_eligibility_summary_response(
                member_health_plan,
                pverify_request,
                pverify_response_with_error_message,
                CostSharingCategory.CONSULTATION,
            )

        rte_transaction = RTETransaction.query.filter(
            RTETransaction.member_health_plan_id == member_health_plan.id
        ).one()
        assert rte_transaction.response_code == 200
        assert rte_transaction.request == pverify_request
        assert (
            rte_transaction.error_message
            == "Payer is not supported for test transaction"
        )

    def test_pverify_inactive_plan_returned(
        self,
        member_health_plan,
        pverify_api,
        pverify_request,
        pverify_response_with_inactive_plan,
    ):
        with pytest.raises(PverifyPlanInactiveError):
            pverify_api._handle_eligibility_summary_response(
                member_health_plan,
                pverify_request,
                pverify_response_with_inactive_plan,
                CostSharingCategory.CONSULTATION,
            )

        rte_transaction = RTETransaction.query.filter(
            RTETransaction.member_health_plan_id == member_health_plan.id
        ).one()
        assert rte_transaction.response_code == 200
        assert rte_transaction.request == pverify_request
        assert rte_transaction.plan_active_status is False
        assert rte_transaction.error_message is None

    def test_success(
        self, member_health_plan, pverify_api, pverify_request, pverify_response
    ):
        transaction = pverify_api._handle_eligibility_summary_response(
            plan=member_health_plan,
            request=pverify_request,
            response=pverify_response,
            cost_sharing_category=CostSharingCategory.CONSULTATION,
            treatment_procedure_id=1,
        )
        expected_eligibility_info = {
            "family_deductible": 50_000,
            "individual_oop": 150_000,
            "family_oop": 300_000,
            "individual_deductible_remaining": 0,
            "individual_deductible": 25_000,
            "coinsurance": 0,
            "copay": 2_000,
            "family_deductible_remaining": 25_000,
            "individual_oop_remaining": 79_309,
            "family_oop_remaining": 229_309,
            "coinsurance_max": None,
            "coinsurance_min": None,
            "max_oop_per_covered_individual": None,
            "hra_remaining": None,
            "is_oop_embedded": None,
            "is_deductible_embedded": None,
            "ignore_deductible": False,
        }
        assert transaction.response_code == 200
        assert transaction.request == pverify_request
        assert transaction.response == expected_eligibility_info
        assert transaction.plan_active_status is True
        assert transaction.error_message is None
        assert transaction.trigger_source == "treatment procedure id: 1"

    def test_handle_tier2_success(
        self,
        member_health_plan,
        pverify_api,
        pverify_request,
        pverify_sample_tier2_response_message,
    ):
        transaction = pverify_api._handle_eligibility_summary_response(
            member_health_plan,
            pverify_request,
            pverify_sample_tier2_response_message,
            CostSharingCategory.CONSULTATION,
            is_second_tier=True,
        )
        expected_eligibility_info = {
            "family_deductible": 3000_00,
            "individual_oop": 5000_00,
            "family_oop": 10000_00,
            "individual_deductible_remaining": 1500_00,
            "individual_deductible": 1500_00,
            "coinsurance": None,
            "copay": None,
            "family_deductible_remaining": 2773_45,
            "individual_oop_remaining": 3117_53,
            "family_oop_remaining": 7710_98,
            "coinsurance_max": None,
            "coinsurance_min": None,
            "max_oop_per_covered_individual": None,
            "hra_remaining": None,
            "is_oop_embedded": None,
            "is_deductible_embedded": None,
            "ignore_deductible": False,
        }
        assert transaction.response_code == 200
        assert transaction.request == pverify_request
        assert transaction.response == expected_eligibility_info
        assert transaction.plan_active_status is True
        assert transaction.error_message is None

    def test_handle_tier2_parse_error(
        self,
        member_health_plan,
        pverify_api,
        pverify_request,
        pverify_sample_tier2_response_message,
    ):
        with pytest.raises(PverifyEligibilityInfoParsingError):
            with mock.patch(
                "cost_breakdown.rte.pverify_api.PverifyAPI._tier2_populate_eligibility_info",
                side_effect=Exception("Parse error"),
            ):
                pverify_api._handle_eligibility_summary_response(
                    member_health_plan,
                    pverify_request,
                    pverify_sample_tier2_response_message,
                    CostSharingCategory.CONSULTATION,
                    is_second_tier=True,
                )

    def test_parse_error(
        self,
        member_health_plan,
        pverify_api,
        pverify_request,
        pverify_no_deductible_response,
    ):
        with pytest.raises(PverifyEligibilityInfoParsingError):
            with mock.patch(
                "cost_breakdown.rte.pverify_api.PverifyAPI._populate_eligibility_info",
                side_effect=Exception("Parse error"),
            ):
                pverify_api._handle_eligibility_summary_response(
                    member_health_plan,
                    pverify_request,
                    pverify_no_deductible_response,
                    CostSharingCategory.CONSULTATION,
                )

    def test_success_no_deductible(
        self,
        member_health_plan,
        pverify_api,
        pverify_request,
        pverify_no_deductible_response,
    ):
        transaction = pverify_api._handle_eligibility_summary_response(
            member_health_plan,
            pverify_request,
            pverify_no_deductible_response,
            CostSharingCategory.CONSULTATION,
        )
        expected_eligibility_info = {
            "family_deductible": None,
            "individual_oop": 300_000,
            "family_oop": 600_000,
            "individual_deductible_remaining": None,
            "individual_deductible": None,
            "coinsurance": 0,
            "copay": 4_000,
            "family_deductible_remaining": None,
            "individual_oop_remaining": 248_274,
            "family_oop_remaining": 540_242,
            "coinsurance_max": None,
            "coinsurance_min": None,
            "max_oop_per_covered_individual": None,
            "hra_remaining": None,
            "is_oop_embedded": None,
            "is_deductible_embedded": None,
            "ignore_deductible": False,
        }
        assert transaction.response_code == 200
        assert transaction.request == pverify_request
        assert transaction.response == expected_eligibility_info
        assert transaction.plan_active_status is True
        assert transaction.error_message is None

    def test_success_empty_fields(
        self,
        member_health_plan,
        pverify_api,
        pverify_request,
        pverify_response_empty_fields,
    ):
        transaction = pverify_api._handle_eligibility_summary_response(
            member_health_plan,
            pverify_request,
            pverify_response_empty_fields,
            CostSharingCategory.CONSULTATION,
        )
        expected_eligibility_info = {
            "family_deductible": 50_000,
            "individual_oop": 150_000,
            "family_oop": 300_000,
            "individual_deductible": 25_000,
            "coinsurance": 0,
            "copay": 2_000,
            "family_deductible_remaining": None,
            "family_oop_remaining": None,
            "individual_deductible_remaining": None,
            "individual_oop_remaining": None,
            "coinsurance_max": None,
            "coinsurance_min": None,
            "max_oop_per_covered_individual": None,
            "hra_remaining": None,
            "is_oop_embedded": None,
            "is_deductible_embedded": None,
            "ignore_deductible": False,
        }
        assert transaction.response_code == 200
        assert transaction.request == pverify_request
        assert transaction.response == expected_eligibility_info
        assert transaction.plan_active_status is True
        assert transaction.error_message is None

    def test_response_containing_hra_remaining(
        self, member_health_plan, pverify_api, pverify_request, pverify_response
    ):
        pverify_response.json()[
            PverifyKeys.ADDITIONAL_INFO.value
        ] = "\r\nTHE MEMBER HAS A HEALTH REIMBURSEMENT ACCOUNT (HRA) BALANCE REMAINING OF 3875.00"
        transaction = pverify_api._handle_eligibility_summary_response(
            member_health_plan,
            pverify_request,
            pverify_response,
            CostSharingCategory.CONSULTATION,
        )
        expected_eligibility_info = {
            "family_deductible": 50_000,
            "individual_oop": 150_000,
            "family_oop": 300_000,
            "individual_deductible_remaining": 0,
            "individual_deductible": 25_000,
            "coinsurance": 0,
            "copay": 2_000,
            "family_deductible_remaining": 25_000,
            "individual_oop_remaining": 79_309,
            "family_oop_remaining": 229_309,
            "coinsurance_max": None,
            "coinsurance_min": None,
            "max_oop_per_covered_individual": None,
            "hra_remaining": 387500,
            "is_oop_embedded": None,
            "is_deductible_embedded": None,
            "ignore_deductible": False,
        }
        assert transaction.response_code == 200
        assert transaction.request == pverify_request
        assert transaction.response == expected_eligibility_info
        assert transaction.plan_active_status is True
        assert transaction.error_message is None


def verify_token_request(mock_request):
    token_data = (
        "grant_type=client_credentials"
        f"&Client_Id={PVERIFY_CLIENT_API_ID}"
        f"&Client_Secret={PVERIFY_CLIENT_API_SECRET}"
    )
    kwargs = mock_request.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == f"{PVERIFY_URL}{TOKEN_ENDPOINT_NAME}"
    assert kwargs["data"] == token_data
    assert kwargs["timeout"] == 30


@freeze_time("2023-01-01 00:00:00")
def test_request_access_token_successful(pverify_api):
    mock_response = requests.Response()
    mock_response.status_code = 200
    seconds_now = datetime(2023, 1, 1, 0, 0).timestamp()
    mock_response.json = lambda: {
        "access_token": "dn0II0uaruxiX7hVoE87Tdgr9-zjDX315e_L8gB0sYpFGFeAy1jMlTdsIunqZGimAxs4",
        "token_type": "bearer",
        "expires_in": 28_799,
    }

    with patch(
        "common.base_http_client.requests.request", return_value=mock_response
    ) as mock_request:
        pverify_api.create_access_token()
        verify_token_request(mock_request)
        assert (
            pverify_api.access_token
            == "dn0II0uaruxiX7hVoE87Tdgr9-zjDX315e_L8gB0sYpFGFeAy1jMlTdsIunqZGimAxs4"
        )
        assert pverify_api.access_token_expiration == seconds_now + 28_799


def test_request_access_token_errors(pverify_api, logs):
    errors = {
        requests.ConnectionError("request failure"): {
            "status": 500,
            "log": "pVerify request failed.",
        },
        requests.HTTPError("request failure"): {
            "status": 418,
            "log": "pVerify request failed with an HTTP status message.",
        },
        requests.Timeout("request timeout"): {
            "status": 408,
            "log": "pVerify request failed due to a connection timeout.",
        },
    }
    with patch("common.base_http_client.requests.request") as mock_request:
        for error, values in errors.items():
            mock_error = error
            mock_error.response = requests.Response()
            mock_error.response.status_code = values["status"]
            mock_request().raise_for_status.side_effect = mock_error
            mock_request.call_count = 0
            pverify_api.create_access_token()
            verify_token_request(mock_request)
            log = next((r for r in logs if values["log"] in r["event"]), None)
            assert mock_request.call_count == 1
            assert pverify_api.access_token == None
            assert pverify_api.access_token_expiration is None
            assert log is not None


@freeze_time("2023-01-01 00:00:00")
def test_get_access_token_none_present(pverify_api):
    mock_response = requests.Response()
    mock_response.status_code = 200
    seconds_now = datetime(2023, 1, 1, 0, 0).timestamp()
    mock_response.json = lambda: {
        "access_token": "token123",
        "token_type": "bearer",
        "expires_in": 28_799,
    }
    with patch(
        "common.base_http_client.requests.request", return_value=mock_response
    ) as mock_response:
        mock_response.call_count = 0
        token = pverify_api.get_access_token()
        assert mock_response.call_count == 1
        assert token == "token123"
        assert pverify_api.access_token == "token123"
        assert pverify_api.access_token_expiration == seconds_now + 28_799


@freeze_time("2023-01-01 00:00:00")
def test_get_access_token_expired(pverify_api):
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "access_token": "token123",
        "token_type": "bearer",
        "expires_in": 28_799,
    }
    seconds_now = datetime(2023, 1, 1, 0, 0).timestamp()
    pverify_api.access_token = "token"
    pverify_api.access_token_expiration = seconds_now - 100
    with patch(
        "common.base_http_client.requests.request", return_value=mock_response
    ) as mock_response:
        mock_response.call_count = 0
        token = pverify_api.get_access_token()
        assert mock_response.call_count == 1
        assert token == "token123"
        assert pverify_api.access_token == "token123"
        assert pverify_api.access_token_expiration == seconds_now + 28799


@freeze_time("2023-01-01 00:00:00")
def test_get_access_token_valid(pverify_api, logs):
    seconds_now = datetime(2023, 1, 1, 0, 0).timestamp()
    pverify_api.access_token = "token"
    pverify_api.access_token_expiration = seconds_now + 100
    with patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.create_access_token",
        return_value="token123",
    ) as mock_create:
        mock_create.call_count = 0
        token = pverify_api.get_access_token()
        refresh_log = next((r for r in logs if "Refresh" in r["event"]), None)
        assert mock_create.call_count == 0
        assert token == "token"
        assert pverify_api.access_token == "token"
        assert pverify_api.access_token_expiration == seconds_now + 100
        assert refresh_log is None


@pytest.mark.parametrize(
    argnames="cost_sharing_category,expected,pverify_key",
    argvalues=[
        (
            CostSharingCategory.CONSULTATION,
            PverifyPracticeCodes.SPECIALIST_OFFICE.value,
            "PRACTICE_CODE",
        ),
        (
            CostSharingCategory.DIAGNOSTIC_MEDICAL,
            PverifyPracticeCodes.DIAGNOSTIC_MEDICAL.value,
            "PRACTICE_CODE",
        ),
        (
            CostSharingCategory.MEDICAL_CARE,
            PverifyPracticeCodes.PRIMARY_CARE.value,
            "PRACTICE_CODE",
        ),
        (
            CostSharingCategory.CONSULTATION,
            PverifyKeys.SPECIALIST_OFFICE_SUMMARY.value,
            "SUMMARY_OBJECT",
        ),
        (
            CostSharingCategory.DIAGNOSTIC_MEDICAL,
            PverifyKeys.DIAGNOSTIC_SUMMARY.value,
            "SUMMARY_OBJECT",
        ),
        (
            CostSharingCategory.MEDICAL_CARE,
            PverifyKeys.PRIMARY_CARE_SUMMARY.value,
            "SUMMARY_OBJECT",
        ),
    ],
)
def test_get_pverify_key(cost_sharing_category, expected, pverify_key):
    returned = get_pverify_key(cost_sharing_category, pverify_key)
    assert returned == expected


def test_get_pverify_key_raises_error():
    assert get_pverify_key(CostSharingCategory.CONSULTATION, "INVALID KEY") is None


@pytest.mark.parametrize(
    argnames="first_name,last_name",
    argvalues=[("fiona", None), (None, "fee"), (None, None)],
)
def test_get_eligibility_summary_request_body_missing_member_names(
    pverify_api,
    first_name,
    last_name,
    member_health_plan_dependent,
    member_health_plan,
):
    with pytest.raises(NoPatientNameFoundError):
        pverify_api._get_eligibility_summary_request_body(
            member_health_plan_dependent,
            "30",
            first_name,
            last_name,
            service_start_date=date(year=2023, month=1, day=1),
        )


def test_get_real_time_eligibility_data_missing_dependent(
    pverify_api, member_health_plan_dependent
):
    with pytest.raises(NoPatientNameFoundError):
        response = pverify_api.get_real_time_eligibility_data(
            member_health_plan_dependent, "30", None, None
        )
        assert response is None
