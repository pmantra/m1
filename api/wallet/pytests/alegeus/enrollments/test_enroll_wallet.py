from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest import mock
from unittest.mock import PropertyMock, patch

import factory
import pytest
from requests import Response
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from authn.models.user import User
from eligibility.pytests import factories as e9y_factories
from pytests import factories
from wallet.alegeus_api import is_request_successful
from wallet.models.constants import AlegeusCoverageTier, BenefitTypes, WalletState
from wallet.models.reimbursement import ReimbursementAccount, ReimbursementPlan
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import (
    ReimbursementAccountFactory,
    ReimbursementAccountTypeFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletPlanHDHPFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory
from wallet.utils.alegeus.enrollments import enroll_wallet
from wallet.utils.alegeus.enrollments.enroll_wallet import (
    _get_wallet_plan_start_date,
    update_member_accounts,
)


@pytest.fixture(autouse=True)
def _mock_e9y(mock_e9y):
    with mock.patch("wallet.utils.alegeus.enrollments.enroll_wallet.e9y", new=mock_e9y):
        yield mock_e9y


def test_was_successful__200():
    response = Response()
    response.status_code = 200

    assert is_request_successful(response) is True


def test_was_successful__400():
    response = Response()
    response.status_code = 400

    assert is_request_successful(response) is False


def test_was_successful__no_status_code():
    response = Response()

    assert is_request_successful(response) is False


@pytest.mark.parametrize(
    "status_code,expected_success",
    [
        (200, True),
        (418, False),
    ],
    ids=["success", "failure"],
)
def test_create_employee_demographic(
    status_code,
    expected_success,
    qualified_alegeus_wallet_hdhp_single,
    qualified_wallet_enablement_hdhp_single,
    mock_e9y,
):
    mock_response = Response()
    mock_response.status_code = status_code
    mock_response.json = lambda: {}
    mock_e9y.wallet_enablement_by_org_identity_search.return_value = (
        qualified_wallet_enablement_hdhp_single
    )

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.post_employee_services_and_banking"
    ) as mock_request:
        mock_request.return_value = mock_response

        was_successful, response = enroll_wallet.create_employee_demographic(
            api, qualified_alegeus_wallet_hdhp_single
        )

        assert was_successful is expected_success
        assert response == mock_response


def test_get_employee_demographic__successful(qualified_alegeus_wallet_hdhp_single):
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_demographic"
    ) as mock_request:
        mock_request.return_value = mock_response

        was_successful = enroll_wallet.get_employee_demographic(
            api, qualified_alegeus_wallet_hdhp_single
        )

        assert was_successful is True


def test_get_employee_demographic__failure_with_null_body(
    qualified_alegeus_wallet_hdhp_single,
):
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: None

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_demographic"
    ) as mock_request:
        mock_request.return_value = mock_response

        was_successful = enroll_wallet.get_employee_demographic(
            api, qualified_alegeus_wallet_hdhp_single
        )

        assert was_successful is False


def test_get_employee_demographic__failure(qualified_alegeus_wallet_hdhp_single):
    mock_response = Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_demographic"
    ) as mock_request:
        mock_request.return_value = mock_response

        was_successful = enroll_wallet.get_employee_demographic(
            api, qualified_alegeus_wallet_hdhp_single
        )

        assert was_successful is False


@pytest.mark.parametrize(
    "status_code,expected_success",
    [
        (200, True),
        (418, False),
    ],
    ids=["success", "failure"],
)
def test_create_dependent_demographics(
    status_code,
    expected_success,
    qualified_alegeus_wallet_with_dependents,
):
    mock_response = Response()
    mock_response.status_code = status_code
    mock_response.json = lambda: {}

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.post_dependent_services"
    ) as mock_request:
        mock_request.return_value = mock_response

        dependent = qualified_alegeus_wallet_with_dependents.authorized_users[0]
        first_name = getattr(dependent, "first_name", "")
        last_name = getattr(dependent, "last_name", "")
        was_successful, response = enroll_wallet.create_dependent_demographic(
            api,
            qualified_alegeus_wallet_with_dependents,
            dependent.alegeus_dependent_id,
            first_name,
            last_name,
        )

        assert was_successful is expected_success
        assert mock_request.call_count == 1
        assert response == mock_response


def test_get_dependents__successful(
    qualified_alegeus_wallet_with_dependents, alegeus_api
):
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {"DepId": "123"},
        {"DepId": "456"},
    ]

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_all_dependents"
    ) as mock_request:
        mock_request.return_value = mock_response

        was_successful, dependents = enroll_wallet.get_dependents(
            alegeus_api, qualified_alegeus_wallet_with_dependents
        )

        assert was_successful is True
        assert len(dependents) == 2
        assert mock_request.call_count == 1


def test_get_dependents__failure(qualified_alegeus_wallet_with_dependents, alegeus_api):
    mock_response = Response()
    mock_response.status_code = 418
    mock_response.json = lambda: []

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_all_dependents"
    ) as mock_request:
        mock_request.return_value = mock_response

        was_successful, dependents = enroll_wallet.get_dependents(
            alegeus_api, qualified_alegeus_wallet_with_dependents
        )

        assert was_successful is False
        assert len(dependents) == 0
        assert mock_request.call_count == 1


def test_get_dependent_demographic__successful(
    qualified_alegeus_wallet_with_dependents, alegeus_api
):
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_dependent_demographic"
    ) as mock_request:
        mock_request.return_value = mock_response

        dependent = qualified_alegeus_wallet_with_dependents.authorized_users[0]
        was_successful = enroll_wallet.get_dependent_demographic(
            alegeus_api, qualified_alegeus_wallet_with_dependents, dependent
        )

        assert was_successful is True
        assert mock_request.call_count == 1


def test_get_dependent_demographic__failure(
    qualified_alegeus_wallet_with_dependents, alegeus_api
):
    mock_response = Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_dependent_demographic"
    ) as mock_request:
        mock_request.return_value = mock_response

        dependent = qualified_alegeus_wallet_with_dependents.authorized_users[0]
        was_successful = enroll_wallet.get_dependent_demographic(
            alegeus_api, qualified_alegeus_wallet_with_dependents, dependent
        )

        assert was_successful is False
        assert mock_request.call_count == 1


def test_create_employee_account__successful_with_dependents(
    qualified_alegeus_wallet_with_dependents, valid_alegeus_plan_hdhp
):
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.post_add_employee_account"
    ) as mock_req_1, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.create_reimbursement_account_from_alegeus"
    ) as mock_req_2, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.post_link_dependent_to_employee_account"
    ) as mock_req_3:
        mock_req_1.return_value = mock_response
        mock_req_2.return_value = (True, [])
        mock_req_3.return_value = mock_response

        was_successful = enroll_wallet.create_employee_account(
            api=api,
            wallet=qualified_alegeus_wallet_with_dependents,
            plan=valid_alegeus_plan_hdhp,
            prefunded_amount=100,
            coverage_tier=None,
            start_date=valid_alegeus_plan_hdhp.start_date,
        )

        assert was_successful == (True, [])
        assert mock_req_1.call_count == 1
        assert mock_req_2.call_count == 1
        assert mock_req_3.call_count == 2


def test_create_employee_account__successful_no_dependents(
    qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp
):
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.post_add_employee_account"
    ) as mock_req_1, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.create_reimbursement_account_from_alegeus"
    ) as mock_req_2, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.post_link_dependent_to_employee_account"
    ) as mock_req_3:
        mock_req_1.return_value = mock_response
        mock_req_2.return_value = (True, [])
        mock_req_3.return_value = mock_response

        was_successful = enroll_wallet.create_employee_account(
            api=api,
            wallet=qualified_alegeus_wallet_hdhp_single,
            plan=valid_alegeus_plan_hdhp,
            prefunded_amount=100,
            coverage_tier=None,
            start_date=valid_alegeus_plan_hdhp.start_date,
        )

        assert was_successful == (True, [])
        assert mock_req_1.call_count == 1
        assert mock_req_2.call_count == 1
        assert mock_req_3.call_count == 0


def test_create_employee_account__unsuccessful_add_employee_account(
    qualified_alegeus_wallet_with_dependents, valid_alegeus_plan_hdhp
):
    mock_response_418 = Response()
    mock_response_418.status_code = 418
    mock_response_418.json = lambda: {}

    mock_response_200 = Response()
    mock_response_200.status_code = 200
    mock_response_200.json = lambda: {}

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.post_add_employee_account"
    ) as mock_req_1, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.create_reimbursement_account_from_alegeus"
    ) as mock_req_2, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.post_link_dependent_to_employee_account"
    ) as mock_req_3:
        mock_req_1.return_value = mock_response_418
        mock_req_2.return_value = (True, [])
        mock_req_3.return_value = mock_response_200

        was_successful = enroll_wallet.create_employee_account(
            api=api,
            wallet=qualified_alegeus_wallet_with_dependents,
            plan=valid_alegeus_plan_hdhp,
            prefunded_amount=100,
            coverage_tier=None,
            start_date=valid_alegeus_plan_hdhp.start_date,
        )

        assert was_successful[0] is False
        assert mock_req_1.call_count == 1
        assert mock_req_2.call_count == 0
        assert mock_req_3.call_count == 0


def test_create_employee_account__unsuccessful_create_reimbursement_account_from_alegeus(
    qualified_alegeus_wallet_with_dependents, valid_alegeus_plan_hdhp
):
    mock_response_200 = Response()
    mock_response_200.status_code = 200
    mock_response_200.json = lambda: {}

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.post_add_employee_account"
    ) as mock_req_1, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.create_reimbursement_account_from_alegeus"
    ) as mock_req_2, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.post_link_dependent_to_employee_account"
    ) as mock_req_3:
        mock_req_1.return_value = mock_response_200
        mock_req_2.return_value = (False, ["Error Message"])
        mock_req_3.return_value = mock_response_200

        was_successful = enroll_wallet.create_employee_account(
            api=api,
            wallet=qualified_alegeus_wallet_with_dependents,
            plan=valid_alegeus_plan_hdhp,
            prefunded_amount=100,
            coverage_tier=None,
            start_date=valid_alegeus_plan_hdhp.start_date,
        )

        assert was_successful[0] is False
        assert mock_req_1.call_count == 1
        assert mock_req_2.call_count == 1
        assert mock_req_3.call_count == 0


def test_create_employee_account__unsuccessful_link_dependents_all_failed(
    qualified_alegeus_wallet_with_dependents, valid_alegeus_plan_hdhp
):
    mock_response_418 = Response()
    mock_response_418.status_code = 418
    mock_response_418.json = lambda: {}

    mock_response_200 = Response()
    mock_response_200.status_code = 200
    mock_response_200.json = lambda: {}

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.post_add_employee_account"
    ) as mock_req_1, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.create_reimbursement_account_from_alegeus"
    ) as mock_req_2, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.post_link_dependent_to_employee_account"
    ) as mock_req_3:
        mock_req_1.return_value = mock_response_200
        mock_req_2.return_value = (True, [])
        mock_req_3.return_value = mock_response_418

        was_successful = enroll_wallet.create_employee_account(
            api=api,
            wallet=qualified_alegeus_wallet_with_dependents,
            plan=valid_alegeus_plan_hdhp,
            prefunded_amount=100,
            coverage_tier=None,
            start_date=valid_alegeus_plan_hdhp.start_date,
        )

        assert was_successful[0] is False
        assert mock_req_1.call_count == 1
        assert mock_req_2.call_count == 1
        assert mock_req_3.call_count == 2


def test_create_employee_account__unsuccessful_link_dependents_some_failed(
    qualified_alegeus_wallet_with_dependents, valid_alegeus_plan_hdhp
):
    mock_response_418 = Response()
    mock_response_418.status_code = 418
    mock_response_418.json = lambda: {}

    mock_response_200 = Response()
    mock_response_200.status_code = 200
    mock_response_200.json = lambda: {}

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.post_add_employee_account"
    ) as mock_req_1, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.create_reimbursement_account_from_alegeus"
    ) as mock_req_2, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.post_link_dependent_to_employee_account"
    ) as mock_req_3:
        mock_req_1.return_value = mock_response_200
        mock_req_2.return_value = (True, [])
        mock_req_3.side_effect = [mock_response_200, mock_response_418]

        was_successful = enroll_wallet.create_employee_account(
            api=api,
            wallet=qualified_alegeus_wallet_with_dependents,
            plan=valid_alegeus_plan_hdhp,
            prefunded_amount=100,
            coverage_tier=None,
            start_date=valid_alegeus_plan_hdhp.start_date,
        )

        assert was_successful[0] is False
        assert mock_req_1.call_count == 1
        assert mock_req_2.call_count == 1
        assert mock_req_3.call_count == 2


def test_get_employee_account__successful(
    qualified_alegeus_wallet_hdhp_single, valid_alegeus_account_hdhp, alegeus_api
):
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "AccountType": "HRA",
    }

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_account_details"
    ) as mock_request:
        mock_request.return_value = mock_response

        success, account_details = enroll_wallet.get_employee_account(
            alegeus_api,
            qualified_alegeus_wallet_hdhp_single,
            valid_alegeus_account_hdhp,
        )

        assert success is True
        assert account_details["AccountType"] == "HRA"
        assert mock_request.call_count == 1


def test_get_employee_account__failure(
    qualified_alegeus_wallet_hdhp_single, valid_alegeus_account_hdhp, alegeus_api
):
    mock_response = Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_account_details"
    ) as mock_request:
        mock_request.return_value = mock_response

        success, account_details = enroll_wallet.get_employee_account(
            alegeus_api,
            qualified_alegeus_wallet_hdhp_single,
            valid_alegeus_account_hdhp,
        )

        assert success is False
        assert account_details is None
        assert mock_request.call_count == 1


def test_create_reimbursement_account_from_alegeus__success(
    qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp
):
    assert ReimbursementAccount.query.count() == 0
    assert not qualified_alegeus_wallet_hdhp_single.authorized_users

    api = enroll_wallet.AlegeusApi()

    # The AcctStatusCde in the response maps to ReimbursementAccountStatus in ReimbursementAccount
    mock_get_account_summary_response = Response()
    mock_get_account_summary_response.status_code = 200
    mock_get_account_summary_response.json = lambda: [
        {
            "PlanId": valid_alegeus_plan_hdhp.alegeus_plan_id,
            "AcctStatusCde": 2,
            "AccountType": "DTR",
            "FlexAccountKey": 17,
        }
    ]

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_account_summary"
    ) as mock_get_account_summary:
        mock_get_account_summary.return_value = mock_get_account_summary_response

        response = enroll_wallet.create_reimbursement_account_from_alegeus(
            api, qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp
        )

        # Assert that Reimbursement Account has been committed with that plan id
        assert response == (True, None)
        assert mock_get_account_summary.call_count == 1

        assert ReimbursementAccount.query.count() == 1


def test_create_reimbursement_account_from_alegeus__unsuccessful_get_account_summary(
    qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp
):
    assert ReimbursementAccount.query.count() == 0
    assert not qualified_alegeus_wallet_hdhp_single.authorized_users

    api = enroll_wallet.AlegeusApi()

    # The AcctStatusCde in the response maps to ReimbursementAccountStatus in ReimbursementAccount
    mock_get_account_summary_response = Response()
    mock_get_account_summary_response.status_code = 418
    mock_get_account_summary_response.json = lambda: {"error": "I am an error message."}
    mock_get_account_summary_response._content = json.dumps(
        {"error": "I am an error message."}
    ).encode()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_account_summary"
    ) as mock_get_account_summary:
        mock_get_account_summary.return_value = mock_get_account_summary_response

        response = enroll_wallet.create_reimbursement_account_from_alegeus(
            api, qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp
        )

        # Assert that Reimbursement Account has been committed with that plan id
        assert response == (False, '{"error": "I am an error message."}')
        assert mock_get_account_summary.call_count == 1
        assert ReimbursementAccount.query.count() == 0


def test_create_reimbursement_account_from_alegeus__unsuccessful_plan_mismatch(
    qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp
):
    assert ReimbursementAccount.query.count() == 0
    assert not qualified_alegeus_wallet_hdhp_single.authorized_users

    api = enroll_wallet.AlegeusApi()

    # The AcctStatusCde in the response maps to ReimbursementAccountStatus in ReimbursementAccount
    content = {
        "PlanId": "mismatched_id",
        "AcctStatusCde": 2,
        "AccountType": "DTR",
        "FlexAccountKey": 17,
    }
    mock_get_account_summary_response = Response()
    mock_get_account_summary_response.status_code = 200
    mock_get_account_summary_response.json = lambda: [content]
    mock_get_account_summary_response._content = json.dumps(content)

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_account_summary"
    ) as mock_get_account_summary:
        mock_get_account_summary.return_value = mock_get_account_summary_response

        response = enroll_wallet.create_reimbursement_account_from_alegeus(
            api, qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp
        )

        # Assert no Reimbursement Accounts have been created due to the plan id mismatch in the alegeus response
        assert response == (False, None)
        assert mock_get_account_summary.call_count == 1
        assert ReimbursementAccount.query.count() == 0


def test_create_reimbursement_account_from_alegeus__unsuccessful_no_accounts_exist_in_alegeus(
    qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp
):
    assert ReimbursementAccount.query.count() == 0
    assert not qualified_alegeus_wallet_hdhp_single.authorized_users

    api = enroll_wallet.AlegeusApi()

    # The AcctStatusCde in the response maps to ReimbursementAccountStatus in ReimbursementAccount
    mock_get_account_summary_response = Response()
    mock_get_account_summary_response.status_code = 200
    mock_get_account_summary_response.json = lambda: []
    mock_get_account_summary_response._content = json.dumps([])

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_account_summary"
    ) as mock_get_account_summary:
        mock_get_account_summary.return_value = mock_get_account_summary_response

        response = enroll_wallet.create_reimbursement_account_from_alegeus(
            api, qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp
        )

        # Assert no Reimbursement Accounts have been created since there were no accounts in the alegeus response
        assert response == (False, None)
        assert mock_get_account_summary.call_count == 1
        assert ReimbursementAccount.query.count() == 0


def test_create_reimbursement_account_from_alegeus__unsuccessful_unsupported_alegeus_account_response(
    qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp
):
    assert ReimbursementAccount.query.count() == 0
    assert not qualified_alegeus_wallet_hdhp_single.authorized_users

    api = enroll_wallet.AlegeusApi()

    # The AcctStatusCde in the response maps to ReimbursementAccountStatus in ReimbursementAccount
    mock_get_account_summary_response = Response()
    mock_get_account_summary_response.status_code = 200

    # We expect a list of objects as the response, receiving an object would break our contract
    mock_get_account_summary_response.json = lambda: [
        {
            "PlanId": valid_alegeus_plan_hdhp.alegeus_plan_id,
            "AcctStatusCde": "ACTIVE",  # dummy false status code to trigger the error
            "AccountType": "DTR",
            "FlexAccountKey": 17,
        }
    ]

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_account_summary"
    ) as mock_get_account_summary:
        mock_get_account_summary.return_value = mock_get_account_summary_response

        response = enroll_wallet.create_reimbursement_account_from_alegeus(
            api, qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp
        )

        # Assert no Reimbursement Accounts have been created since there were no accounts in the alegeus response
        assert response == (False, "'ACTIVE' is not a valid ReimbursementAccountStatus")
        assert mock_get_account_summary.call_count == 1
        assert ReimbursementAccount.query.count() == 0


@pytest.mark.parametrize(
    "get_employee_demographic_return, "
    "post_add_employee_account_return,"
    "expected_success, "
    "expected_messages",
    [
        (
            True,
            (None, None),
            True,
            ["Found existing Employee in Alegeus"],
        ),
        (
            False,
            (True, mock.MagicMock(text="Mock Valid Response")),
            True,
            [
                "Could not find an existing Employee in Alegeus",
                "Successfully created an Employee in Alegeus",
            ],
        ),
        (
            False,
            (False, mock.MagicMock(text="Mock Invalid Response")),
            False,
            [
                "Could not find an existing Employee in Alegeus",
                "Could not create Employee in Alegeus",
            ],
        ),
    ],
    ids=["successful_existing_employee", "successful_create_employee", "failure"],
)
def test_configure_employee(
    get_employee_demographic_return,
    post_add_employee_account_return,
    expected_success,
    expected_messages,
    qualified_alegeus_wallet_hra,
    alegeus_api,
):
    messages = []
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_demographic",
        return_value=get_employee_demographic_return,
    ), patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.create_employee_demographic",
        return_value=post_add_employee_account_return,
    ):

        was_successful, messages = enroll_wallet.configure_employee(
            alegeus_api, qualified_alegeus_wallet_hra, messages
        )

        assert was_successful is expected_success
        assert len(messages) == len(expected_messages)
        for index, message in enumerate(messages):
            assert message.message.startswith(expected_messages[index])


def test_configure_dependents__success_no_dependents(
    qualified_alegeus_wallet_hdhp_single, alegeus_api
):
    messages = []
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_dependents"
    ) as mock_get_dependents:
        mock_get_dependents.return_value = (True, [])

        was_successful, messages = enroll_wallet.configure_dependents(
            alegeus_api, qualified_alegeus_wallet_hdhp_single, messages
        )

        assert was_successful is True
        assert len(messages) == 1
        assert "no associated dependents" in messages[0].message


@pytest.mark.parametrize(
    "mock_get_deps_return, mock_create_dep_return, expected_call_count, expected_messages",
    [
        (
            (True, [0, 1]),
            [(None, None)],
            0,
            ["Found existing Dependent", "Found existing Dependent"],
        ),
        (
            (True, []),
            [(True, None), (True, None)],
            2,
            [
                "Could not find existing Dependent",
                "Successfully created Dependent",
                "Could not find existing Dependent",
                "Successfully created Dependent",
            ],
        ),
        (
            (True, [0]),
            [(True, None)],
            1,
            [
                "Found existing Dependent",
                "Could not find existing Dependent",
                "Successfully created Dependent",
            ],
        ),
        (
            (False, []),
            [(False, mock.MagicMock(text="Alegeus Error"))],
            1,
            [
                "Could not find existing Dependent",
                "Could not create Dependent",
            ],
        ),
        (
            (False, []),
            [(True, None), (False, mock.MagicMock(text="Alegeus Error"))],
            2,
            [
                "Could not find existing Dependent",
                "Successfully created Dependent",
                "Could not find existing Dependent",
                "Could not create Dependent",
            ],
        ),
    ],
    ids=[
        "success_existing_dependents",
        "success_create_dependents",
        "success_create_some_dependents",
        "failure_creating_first_dependent",
        "failure_creating_second_dependent",
    ],
)
def test_configure_dependents(
    mock_get_deps_return,
    mock_create_dep_return,
    expected_call_count,
    expected_messages,
    alegeus_api,
    qualified_alegeus_wallet_with_dependents,
):
    dependents = qualified_alegeus_wallet_with_dependents.authorized_users
    mock_dependents = [
        {"DepId": dependent.alegeus_dependent_id} for dependent in dependents
    ]
    return_mock_dependents = [
        mock_dependents[i] for i in mock_get_deps_return[1] if mock_get_deps_return[1]
    ]
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_dependents",
        return_value=(mock_get_deps_return[0], return_mock_dependents),
    ), patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.create_dependent_demographic",
        side_effect=mock_create_dep_return,
    ) as mock_create_dependent_demographic:
        was_successful, messages = enroll_wallet.configure_dependents(
            alegeus_api, qualified_alegeus_wallet_with_dependents, []
        )

        assert mock_create_dependent_demographic.call_count == expected_call_count
        assert len(messages) == len(expected_messages)
        for index, flash_message in enumerate(messages):
            assert flash_message.message.startswith(expected_messages[index])


def test_configure_account__successful_create_new_account(
    qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp, alegeus_api
):
    messages = []

    with patch(
        "wallet.models.reimbursement.ReimbursementAccount.query.filter_by"
    ) as mock_account_query, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.create_employee_account"
    ) as mock_create_employee_account:
        mock_account_query.return_value = None
        mock_create_employee_account.return_value = (True, [])

        was_successful, messages = enroll_wallet.configure_account(
            api=alegeus_api,
            wallet=qualified_alegeus_wallet_hdhp_single,
            plan=valid_alegeus_plan_hdhp,
            prefunded_amount=0,
            coverage_tier=None,
            start_date=valid_alegeus_plan_hdhp.start_date,
            messages=messages,
        )

        assert mock_create_employee_account.call_count == 1
        assert was_successful is True
        assert len(messages) == 1
        assert messages[0].message.startswith(
            "Successfully created ReimbursementAccount"
        )


def test_configure_account__successful_existing_account(
    qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp, alegeus_api
):
    messages = []

    account = ReimbursementAccountFactory.create(
        wallet=qualified_alegeus_wallet_hdhp_single,
        plan=valid_alegeus_plan_hdhp,
    )

    with patch(
        "wallet.models.reimbursement.ReimbursementAccount.query"
    ) as mock_account_query, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_account"
    ) as mock_get_employee_account:
        mock_account_query.return_value = account
        mock_get_employee_account.return_value = (True, {})

        was_successful, messages = enroll_wallet.configure_account(
            api=alegeus_api,
            wallet=qualified_alegeus_wallet_hdhp_single,
            plan=valid_alegeus_plan_hdhp,
            prefunded_amount=0,
            coverage_tier=None,
            start_date=valid_alegeus_plan_hdhp.start_date,
            messages=messages,
        )

        assert mock_get_employee_account.call_count == 1
        assert was_successful is True
        assert len(messages) == 1
        assert messages[0].message.startswith("Found existing Account")


def test_configure_account__failure_creating_account(
    qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp, alegeus_api
):
    messages = []

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.create_employee_account"
    ) as mock_create_employee_account:
        mock_create_employee_account.return_value = (
            False,
            [
                FlashMessage(
                    message="Error Message", category=FlashMessageCategory.ERROR
                )
            ],
        )

        was_successful, messages = enroll_wallet.configure_account(
            api=alegeus_api,
            wallet=qualified_alegeus_wallet_hdhp_single,
            plan=valid_alegeus_plan_hdhp,
            prefunded_amount=0,
            coverage_tier=None,
            start_date=valid_alegeus_plan_hdhp.start_date,
            messages=messages,
        )

        assert mock_create_employee_account.call_count == 1
        assert was_successful is False
        assert len(messages) == 2
        assert messages[1].message.startswith("Could not create ReimbursementAccount")
        assert messages[0].message == "Error Message"


def test_configure_account__failure_get_employee_account(
    qualified_alegeus_wallet_hdhp_single, valid_alegeus_plan_hdhp, alegeus_api
):
    messages = []

    account = ReimbursementAccountFactory.create(
        wallet=qualified_alegeus_wallet_hdhp_single,
        plan=valid_alegeus_plan_hdhp,
    )

    with patch(
        "wallet.models.reimbursement.ReimbursementAccount.query"
    ) as mock_account_query, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_account"
    ) as mock_get_employee_account, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.create_employee_account"
    ) as mock_create_employee_account:
        mock_account_query.return_value = account
        mock_get_employee_account.return_value = (False, None)
        mock_create_employee_account.return_value = (
            False,
            [
                FlashMessage(
                    message="Error Message", category=FlashMessageCategory.ERROR
                )
            ],
        )

        was_successful, messages = enroll_wallet.configure_account(
            api=alegeus_api,
            wallet=qualified_alegeus_wallet_hdhp_single,
            plan=valid_alegeus_plan_hdhp,
            prefunded_amount=0,
            coverage_tier=None,
            start_date=valid_alegeus_plan_hdhp.start_date,
            messages=messages,
        )

        assert mock_get_employee_account.call_count == 1
        assert mock_create_employee_account.call_count == 1
        assert was_successful is False
        assert len(messages) == 3
        assert messages[0].message.startswith("Could not find existing Account")
        assert messages[1].message == "Error Message"
        assert messages[2].message.startswith("Could not create Account")


@pytest.mark.disable_auto_patch_configure_wallet
def test_configure_wallet_in_alegeus__successful(
    qualified_alegeus_wallet_with_dependents,
):
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_employee"
    ) as mock_configure_employee, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_dependents"
    ) as mock_configure_dependents, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_employee.return_value = (True, ["1"])
        mock_configure_dependents.return_value = (True, ["1", "2"])
        mock_configure_account.return_value = (True, ["1", "2", "3"])

        was_successful, messages = enroll_wallet.configure_wallet_in_alegeus(
            qualified_alegeus_wallet_with_dependents
        )

        assert mock_configure_employee.call_count == 1
        assert mock_configure_dependents.call_count == 1
        assert mock_configure_account.call_count == 1
        assert was_successful is True
        assert messages == ["1", "2", "3"]


# An alternative to the above test, with a different wallet (that has actual plans
# instead of just an HDHP), and with two types of categories to test the funding
# amounts.
@pytest.mark.disable_auto_patch_configure_wallet
def test_configure_wallet_in_alegeus__alternative_successful(enterprise_user):
    org_settings = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id
    )

    plan_1 = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="HRA"
        ),
        alegeus_plan_id="FERTILITY",
        start_date=date(year=2020, month=1, day=3),
        end_date=date(year=2199, month=12, day=31),
        is_hdhp=False,
    )
    category_1 = ReimbursementRequestCategoryFactory.create(
        label="fertility", reimbursement_plan=plan_1
    )
    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=category_1,
        benefit_type=BenefitTypes.CYCLE,
        num_cycles=2,
    )

    plan_2 = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="HRA"
        ),
        alegeus_plan_id="CHILDCARE",
        start_date=date(year=2020, month=1, day=3),
        end_date=date(year=2199, month=12, day=31),
        is_hdhp=False,
    )
    category_2 = ReimbursementRequestCategoryFactory.create(
        label="childcare", reimbursement_plan=plan_2
    )
    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=category_2,
        reimbursement_request_category_maximum=5_000,
    )

    mixed_benefit_type_wallet = ReimbursementWalletFactory.create(
        state=WalletState.PENDING,
        reimbursement_organization_settings=org_settings,
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=mixed_benefit_type_wallet.id,
    )

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_employee"
    ) as mock_configure_employee, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_dependents"
    ) as mock_configure_dependents, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_employee.return_value = (True, ["1"])
        mock_configure_dependents.return_value = (True, ["1"])
        mock_configure_account.return_value = (True, ["1", "2", "3"])

        was_successful, messages = enroll_wallet.configure_wallet_in_alegeus(
            mixed_benefit_type_wallet
        )

        assert mock_configure_employee.call_count == 1
        assert mock_configure_dependents.call_count == 1
        assert mock_configure_account.call_count == 2
        assert (
            mock_configure_account.call_args_list[0].kwargs["prefunded_amount"]
            == 80_000_00
        )  # 2 cycles
        assert (
            mock_configure_account.call_args_list[1].kwargs["prefunded_amount"] == 5_000
        )  # currency
        assert was_successful is True


@pytest.mark.disable_auto_patch_configure_wallet
@pytest.mark.parametrize(
    argnames=("category_currency", "category_amount", "rate", "usd_amount"),
    argvalues=[
        (None, 5_000, Decimal("1.00"), 5_000),
        ("USD", 5_000, Decimal("1.00"), 5_000),
        ("AUD", 5_000, Decimal("2.00"), 10_000),
        ("NZD", 5_000, Decimal("4.00"), 20_000),
    ],
)
def test_configure_wallet_in_alegeus__alternative_successful_multi_currency(
    enterprise_user: User,
    category_currency: str | None,
    category_amount: int,
    rate: Decimal,
    usd_amount: int,
):
    org_settings = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id
    )

    plan_1 = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="HRA"
        ),
        alegeus_plan_id="FERTILITY",
        start_date=date(year=2020, month=1, day=3),
        end_date=date(year=2199, month=12, day=31),
        is_hdhp=False,
    )
    category_1 = ReimbursementRequestCategoryFactory.create(
        label="fertility", reimbursement_plan=plan_1
    )
    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=category_1,
        benefit_type=BenefitTypes.CYCLE,
        num_cycles=2,
    )

    plan_2 = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="HRA"
        ),
        alegeus_plan_id="CHILDCARE",
        start_date=date(year=2020, month=1, day=3),
        end_date=date(year=2199, month=12, day=31),
        is_hdhp=False,
    )
    category_2 = ReimbursementRequestCategoryFactory.create(
        label="childcare", reimbursement_plan=plan_2
    )
    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=category_2,
        reimbursement_request_category_maximum=category_amount,
        currency_code=category_currency,
    )

    mixed_benefit_type_wallet = ReimbursementWalletFactory.create(
        state=WalletState.PENDING,
        reimbursement_organization_settings=org_settings,
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=mixed_benefit_type_wallet.id,
    )

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_employee"
    ) as mock_configure_employee, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_dependents"
    ) as mock_configure_dependents, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account, patch(
        "wallet.repository.currency_fx_rate.CurrencyFxRateRepository.get_rate"
    ) as mock_get_rate:
        mock_configure_employee.return_value = (True, ["1"])
        mock_configure_dependents.return_value = (True, ["1"])
        mock_configure_account.return_value = (True, ["1", "2", "3"])
        mock_get_rate.return_value = rate

        was_successful, messages = enroll_wallet.configure_wallet_in_alegeus(
            mixed_benefit_type_wallet
        )

        assert mock_configure_employee.call_count == 1
        assert mock_configure_dependents.call_count == 1
        assert mock_configure_account.call_count == 2
        assert (
            mock_configure_account.call_args_list[0].kwargs["prefunded_amount"]
            == 80_000_00
        )  # 2 cycles
        assert (
            mock_configure_account.call_args_list[1].kwargs["prefunded_amount"]
            == usd_amount
        )  # currency
        assert was_successful is True


@pytest.mark.disable_auto_patch_configure_wallet
def test_configure_wallet_in_alegeus__failure_configure_employee(
    qualified_alegeus_wallet_with_dependents,
):
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_employee"
    ) as mock_configure_employee, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_dependents"
    ) as mock_configure_dependents, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_employee.return_value = (False, ["1"])
        mock_configure_dependents.return_value = (True, ["1", "2"])
        mock_configure_account.return_value = (True, ["1", "2", "3"])

        was_successful, messages = enroll_wallet.configure_wallet_in_alegeus(
            qualified_alegeus_wallet_with_dependents
        )

        assert mock_configure_employee.call_count == 1
        assert mock_configure_dependents.call_count == 0
        assert mock_configure_account.call_count == 0
        assert was_successful is False
        assert messages == ["1"]


@pytest.mark.disable_auto_patch_configure_wallet
def test_configure_wallet_in_alegeus__failure_configure_dependents(
    qualified_alegeus_wallet_with_dependents,
):
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_employee"
    ) as mock_configure_employee, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_dependents"
    ) as mock_configure_dependents, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_employee.return_value = (True, ["1"])
        mock_configure_dependents.return_value = (False, ["1", "2"])
        mock_configure_account.return_value = (True, ["1", "2", "3"])

        was_successful, messages = enroll_wallet.configure_wallet_in_alegeus(
            qualified_alegeus_wallet_with_dependents
        )

        assert mock_configure_employee.call_count == 1
        assert mock_configure_dependents.call_count == 1
        assert mock_configure_account.call_count == 0
        assert was_successful is False
        assert messages == ["1", "2"]


@pytest.mark.disable_auto_patch_configure_wallet
def test_configure_wallet_in_alegeus__failure_configure_account(
    qualified_alegeus_wallet_with_dependents,
):
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_employee"
    ) as mock_configure_employee, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_dependents"
    ) as mock_configure_dependents, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_employee.return_value = (True, ["1"])
        mock_configure_dependents.return_value = (True, ["1", "2"])
        mock_configure_account.return_value = (False, ["1", "2", "3"])

        was_successful, messages = enroll_wallet.configure_wallet_in_alegeus(
            qualified_alegeus_wallet_with_dependents
        )

        assert mock_configure_employee.call_count == 1
        assert mock_configure_dependents.call_count == 1
        assert mock_configure_account.call_count == 1
        assert was_successful is False
        assert messages == ["1", "2", "3"]


@pytest.mark.disable_auto_patch_configure_wallet
def test_configure_wallet_in_alegeus__failure_configure_account_no_allowed_categories(
    qualified_alegeus_wallet_with_dependents,
):
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_employee"
    ) as mock_configure_employee, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_dependents"
    ) as mock_configure_dependents, patch.object(
        ReimbursementWallet,
        "get_wallet_allowed_categories",
        new_callable=PropertyMock,
    ) as mock_allowed_categories:
        mock_configure_employee.return_value = (True, ["1"])
        mock_configure_dependents.return_value = (True, ["1", "2"])
        qualified_alegeus_wallet_with_dependents.reimbursement_hdhp_plans = []
        mock_allowed_categories.return_value = []

        was_successful, messages = enroll_wallet.configure_wallet_in_alegeus(
            qualified_alegeus_wallet_with_dependents
        )

        assert mock_configure_employee.call_count == 1
        assert mock_configure_dependents.call_count == 1
        assert was_successful is False


def test_get_eligibility_date_from_wallet__date_is_after_plan_start(
    qualified_alegeus_wallet_hra,
    qualified_wallet_enablement_hra,
    valid_alegeus_plan_hra,
    mock_e9y,
):
    yesterday = datetime.utcnow() - timedelta(days=1)
    valid_alegeus_plan_hra.start_date = yesterday.date()
    mock_e9y.grpc_service.wallet_enablement_by_user_id_search.return_value = (
        qualified_wallet_enablement_hra
    )
    verification = e9y_factories.build_verification_from_wallet(
        qualified_alegeus_wallet_hra
    )
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        eligibility_date = enroll_wallet.get_eligibility_date_from_wallet(
            qualified_alegeus_wallet_hra
        )

        assert eligibility_date
        assert eligibility_date == qualified_wallet_enablement_hra.eligibility_date


def test_get_eligibility_date_is_wallet_enablement_created_at(
    qualified_alegeus_wallet_hra,
    qualified_wallet_enablement_hra,
    valid_alegeus_plan_hra,
    mock_e9y,
):
    past = datetime.utcnow() - timedelta(days=3)
    way_in_the_past = datetime.utcnow() - timedelta(days=7)
    valid_alegeus_plan_hra.start_date = way_in_the_past.date()
    qualified_wallet_enablement_hra.created_at = past

    mock_e9y.grpc_service.wallet_enablement_by_user_id_search.return_value = (
        qualified_wallet_enablement_hra
    )
    eligibility_date = enroll_wallet.get_eligibility_date_from_wallet(
        qualified_alegeus_wallet_hra
    )

    assert eligibility_date
    assert eligibility_date == qualified_wallet_enablement_hra.created_at.date()


def test_get_eligibility_date_from_wallet_eligibility_date_is_before_plan_start(
    qualified_alegeus_wallet_hra,
    qualified_wallet_enablement_hra,
    valid_alegeus_plan_hra,
    mock_e9y,
):
    days_ago = datetime.utcnow() - timedelta(days=4)
    valid_alegeus_plan_hra.start_date = datetime.utcnow().date()
    qualified_wallet_enablement_hra.eligibility_date = days_ago.date()

    mock_e9y.grpc_service.wallet_enablement_by_user_id_search.return_value = (
        qualified_wallet_enablement_hra
    )

    eligibility_date = enroll_wallet.get_eligibility_date_from_wallet(
        qualified_alegeus_wallet_hra
    )
    assert eligibility_date == valid_alegeus_plan_hra.start_date


def test_get_eligibility_date_from_wallet__eligibility_date_is_None(
    qualified_alegeus_wallet_hra,
    qualified_wallet_enablement_hra,
    valid_alegeus_plan_hra,
    mock_e9y,
):
    valid_alegeus_plan_hra.start_date = datetime.utcnow().date()
    qualified_wallet_enablement_hra.start_date = None
    qualified_wallet_enablement_hra.created_at = None
    qualified_wallet_enablement_hra.eligibility_date = None
    mock_e9y.grpc_service.wallet_enablement_by_user_id_search.return_value = (
        qualified_wallet_enablement_hra
    )
    eligibility_date = enroll_wallet.get_eligibility_date_from_wallet(
        qualified_alegeus_wallet_hra
    )
    assert eligibility_date == valid_alegeus_plan_hra.start_date


def test_get_eligibility_date_from_wallet__verification_created_at_is_after_plan_start(
    qualified_alegeus_wallet_hra,
    qualified_wallet_enablement_hra,
    valid_alegeus_plan_hra,
    mock_e9y,
):
    yesterday = datetime.utcnow() - timedelta(days=1)
    valid_alegeus_plan_hra.start_date = yesterday.date()
    qualified_wallet_enablement_hra.started_at = None
    qualified_wallet_enablement_hra.created_at = None
    mock_e9y.grpc_service.wallet_enablement_by_user_id_search.return_value = (
        qualified_wallet_enablement_hra
    )

    verification = e9y_factories.build_verification_from_wallet(
        wallet=qualified_alegeus_wallet_hra,
        created_at=datetime.utcnow(),
    )
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        eligibility_date = enroll_wallet.get_eligibility_date_from_wallet(
            qualified_alegeus_wallet_hra
        )
        assert eligibility_date == verification.created_at.date()


def test_get_eligibility_date_from_wallet_with_no_wallet_enablement_uses_min_verification_date(
    qualified_alegeus_wallet_hra,
    valid_alegeus_plan_hra,
    mock_e9y,
    qualified_verification_hra,
):
    yesterday = datetime.utcnow() - timedelta(days=1)
    valid_alegeus_plan_hra.eligibility_date = datetime.utcnow()
    valid_alegeus_plan_hra.start_date = datetime.utcnow().date() - timedelta(days=31)
    qualified_verification_hra.verified_at = yesterday
    mock_e9y.grpc_service.wallet_enablement_by_user_id_search.return_value = None

    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=qualified_verification_hra,
    ):
        eligibility_date = enroll_wallet.get_eligibility_date_from_wallet(
            qualified_alegeus_wallet_hra
        )
        assert eligibility_date == qualified_verification_hra.verified_at.date()


def test_get_eligibility_date_from_wallet_with_wallet_enablement_provided(
    qualified_alegeus_wallet_hra,
    qualified_wallet_enablement_hra,
    valid_alegeus_plan_hra,
):
    yesterday = datetime.utcnow() - timedelta(days=1)
    valid_alegeus_plan_hra.start_date = yesterday.date()
    verification = e9y_factories.build_verification_from_wallet(
        qualified_alegeus_wallet_hra
    )
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        eligibility_date = enroll_wallet.get_eligibility_date_from_wallet(
            qualified_alegeus_wallet_hra, qualified_wallet_enablement_hra
        )

        assert eligibility_date
        assert eligibility_date == qualified_wallet_enablement_hra.eligibility_date


def test_get_eligibility_date_returns_ey9_start_date(
    qualified_alegeus_wallet_hra,
    qualified_wallet_enablement_hra,
    valid_alegeus_plan_hra,
    mock_e9y,
):
    yesterday = datetime.utcnow() - timedelta(days=1)
    valid_alegeus_plan_hra.start_date = None
    qualified_wallet_enablement_hra.start_date = yesterday.date()
    qualified_wallet_enablement_hra.created_at = None
    mock_e9y.grpc_service.wallet_enablement_by_user_id_search.return_value = (
        qualified_wallet_enablement_hra
    )

    eligibility_date = enroll_wallet.get_eligibility_date_from_wallet(
        qualified_alegeus_wallet_hra
    )
    assert eligibility_date == qualified_wallet_enablement_hra.start_date


def test_get_eligibility_date_returns_ey9_created_at(
    qualified_alegeus_wallet_hra,
    qualified_wallet_enablement_hra,
    valid_alegeus_plan_hra,
    mock_e9y,
):
    yesterday = datetime.utcnow() - timedelta(days=1)
    valid_alegeus_plan_hra.start_date = None
    qualified_wallet_enablement_hra.start_date = None
    qualified_wallet_enablement_hra.created_at = yesterday
    mock_e9y.grpc_service.wallet_enablement_by_user_id_search.return_value = (
        qualified_wallet_enablement_hra
    )

    eligibility_date = enroll_wallet.get_eligibility_date_from_wallet(
        qualified_alegeus_wallet_hra
    )
    assert eligibility_date == qualified_wallet_enablement_hra.created_at.date()


def test_get_eligibility_date_returns_min_verification_date(
    qualified_alegeus_wallet_hra,
    qualified_wallet_enablement_hra,
    valid_alegeus_plan_hra,
    mock_e9y,
    qualified_verification_hra,
):
    valid_alegeus_plan_hra.start_date = None
    qualified_wallet_enablement_hra.start_date = None
    qualified_wallet_enablement_hra.created_at = None
    mock_e9y.grpc_service.wallet_enablement_by_user_id_search.return_value = (
        qualified_wallet_enablement_hra
    )
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=qualified_verification_hra,
    ):
        eligibility_date = enroll_wallet.get_eligibility_date_from_wallet(
            qualified_alegeus_wallet_hra
        )
        assert eligibility_date == qualified_verification_hra.verified_at.date()


@pytest.mark.parametrize(
    "plan_start_date,e9y_date,tenure,expected_date",
    [
        pytest.param(
            date(year=2024, month=6, day=11),
            date(year=2023, month=6, day=15),
            0,
            date(year=2024, month=6, day=11),
            id="e9y < plan start date, no tenure -> plan start date",
        ),
        pytest.param(
            date(year=2024, month=6, day=11),
            date(year=2024, month=9, day=1),
            0,
            date(year=2024, month=9, day=1),
            id="e9y > plan start date, no tenure -> e9y date",
        ),
        pytest.param(
            date(year=2024, month=6, day=11),
            date(year=2024, month=6, day=1),
            30,
            date(year=2024, month=7, day=1),
            id="e9y + tenure > plan start date -> e9y + tenure date",
        ),
        pytest.param(
            date(year=2024, month=6, day=11),
            date(year=2023, month=1, day=1),
            30,
            date(year=2024, month=6, day=11),
            id="e9y + tenure < plan start date -> plan start date",
        ),
        pytest.param(
            date(year=2023, month=1, day=1),
            date(year=2023, month=1, day=1),
            0,
            date(year=2023, month=1, day=1),
            id="e9y == plan start date",
        ),
        pytest.param(
            date(year=2025, month=1, day=1),
            date(year=2024, month=3, day=4),
            90,
            date(year=2025, month=1, day=1),
            id="mock amazon user",
        ),
    ],
)
def test_get_eligibility_date_tenure(
    qualified_alegeus_wallet_hra, plan_start_date, e9y_date, tenure, expected_date
):
    qualified_alegeus_wallet_hra.reimbursement_organization_settings.required_tenure_days = (
        tenure
    )
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet._get_wallet_plan_start_date",
        return_value=plan_start_date,
    ), patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet._get_wallet_eligibility_date",
        return_value=e9y_date,
    ):
        eligibility_date = enroll_wallet.get_eligibility_date_from_wallet(
            qualified_alegeus_wallet_hra
        )
    assert eligibility_date == expected_date


@pytest.mark.parametrize(
    "size,labels,start_dates,expected",
    [
        (0, [], [], None),
        (
            1,
            ["Test 1"],
            [date(year=2024, month=1, day=1)],
            date(year=2024, month=1, day=1),
        ),
        (
            2,
            ["Test 1", "Test 2"],
            [date(year=2023, month=1, day=1), date(year=2024, month=1, day=1)],
            date(year=2023, month=1, day=1),
        ),
        (
            3,
            ["Test 1", "Test 2", "Test 3"],
            [
                date(year=2024, month=1, day=1),
                date(year=2024, month=5, day=5),
                date(year=2023, month=1, day=2),
            ],
            date(year=2023, month=1, day=2),
        ),
    ],
)
def test__get_wallet_plan_start_date(
    qualified_alegeus_wallet_hra, size, labels, start_dates, expected
):
    plans = ReimbursementPlanFactory.create_batch(
        size=size,
        start_date=factory.Iterator(start_dates),
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
    )
    # remove any categories that were created under the hood.
    ReimbursementOrgSettingCategoryAssociation.query.delete()
    categories = ReimbursementRequestCategoryFactory.create_batch(
        size=size,
        label=factory.Iterator(labels),
        reimbursement_plan=factory.Iterator(plans),
    )
    _ = ReimbursementOrgSettingCategoryAssociationFactory.create_batch(
        size=size,
        reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings_id,
        reimbursement_request_category=factory.Iterator(categories),
    )
    result = _get_wallet_plan_start_date(qualified_alegeus_wallet_hra)
    assert result == expected


def test_check_hdhp_status__no_hdhp_plans(qualified_alegeus_wallet_hra):
    hdhp_status = enroll_wallet.check_hdhp_status(qualified_alegeus_wallet_hra)
    assert hdhp_status is None


def test_check_hdhp_status__invalid_hdhp_plan(qualified_alegeus_wallet_hra):
    # a hdhp plan without `reimbursement_plan` attribute
    ReimbursementWalletPlanHDHPFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        alegeus_coverage_tier=AlegeusCoverageTier.SINGLE,
    )

    hdhp_status = enroll_wallet.check_hdhp_status(qualified_alegeus_wallet_hra)
    assert hdhp_status is None


def test_check_hdhp_status__no_current_hdhp_plan(qualified_alegeus_wallet_hra):
    wallet = qualified_alegeus_wallet_hra

    plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="DTR"
        ),
        alegeus_plan_id="HDHP",
        start_date=date(year=2020, month=1, day=3),
        end_date=date(year=2020, month=12, day=31),
        is_hdhp=True,
    )
    _add_hdhp_plan_to_wallet(wallet, plan)

    hdhp_status = enroll_wallet.check_hdhp_status(wallet)
    assert hdhp_status is None


def test_check_hdhp_status__api_failure(
    qualified_alegeus_wallet_hra, current_hdhp_plan
):
    wallet = qualified_alegeus_wallet_hra
    _add_hdhp_plan_to_wallet(wallet, current_hdhp_plan)

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_accounts"
    ) as mock_get_employee_accounts:
        mock_get_employee_accounts.return_value = (False, None)

        status = enroll_wallet.check_hdhp_status(wallet)
        assert status is False


def test_check_hdhp_status__missing_account(
    qualified_alegeus_wallet_hra, current_hdhp_plan
):
    wallet = qualified_alegeus_wallet_hra
    _add_hdhp_plan_to_wallet(wallet, current_hdhp_plan)

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_accounts"
    ) as mock_get_employee_accounts:
        mock_get_employee_accounts.return_value = (
            True,
            [
                {
                    "AccountType": "HRA",
                    "PlanId": "NOT_CURRENT",
                },
            ],
        )

        status = enroll_wallet.check_hdhp_status(wallet)
        assert status is False


def test_check_hdhp_status__missing_balances(
    qualified_alegeus_wallet_hra, current_hdhp_plan
):
    wallet = qualified_alegeus_wallet_hra
    _add_hdhp_plan_to_wallet(wallet, current_hdhp_plan)

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_accounts"
    ) as mock_get_employee_accounts:
        mock_get_employee_accounts.return_value = (
            True,
            [
                {
                    "AccountType": "HRA",
                    "PlanId": current_hdhp_plan.alegeus_plan_id,
                },
            ],
        )

        status = enroll_wallet.check_hdhp_status(wallet)
        assert status is False


def test_check_hdhp_status__unmet(qualified_alegeus_wallet_hra, current_hdhp_plan):
    wallet = qualified_alegeus_wallet_hra
    _add_hdhp_plan_to_wallet(wallet, current_hdhp_plan)

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_accounts"
    ) as mock_get_employee_accounts:
        mock_get_employee_accounts.return_value = (
            True,
            [
                {
                    "AccountType": "HRA",
                    "AnnualElection": 1400.00,
                    "AvailBalance": 1.99,
                    "PlanId": current_hdhp_plan.alegeus_plan_id,
                },
            ],
        )

        status = enroll_wallet.check_hdhp_status(wallet)
        assert status is False


def test_check_hdhp_status__met(qualified_alegeus_wallet_hra, current_hdhp_plan):
    wallet = qualified_alegeus_wallet_hra
    _add_hdhp_plan_to_wallet(wallet, current_hdhp_plan)

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_accounts"
    ) as mock_get_employee_accounts:
        mock_get_employee_accounts.return_value = (
            True,
            [
                {
                    "AccountType": "HRA",
                    "AnnualElection": 1400.00,
                    "AvailBalance": 0.00,
                    "PlanId": current_hdhp_plan.alegeus_plan_id,
                },
            ],
        )

        status = enroll_wallet.check_hdhp_status(wallet)
        assert status is True


def _add_hdhp_plan_to_wallet(wallet: ReimbursementWallet, plan: ReimbursementPlan):
    ReimbursementWalletPlanHDHPFactory.create(
        reimbursement_plan=plan,
        wallet=wallet,
        alegeus_coverage_tier=AlegeusCoverageTier.SINGLE,
    )
    ReimbursementAccountFactory.create(
        alegeus_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="DTR"
        ),
        alegeus_flex_account_key="42",
        wallet=wallet,
        plan=plan,
    )


def test_get_alegeus_hdhp_plan_year_to_date_spend(
    qualified_alegeus_wallet_hra, current_hdhp_plan
):
    wallet = qualified_alegeus_wallet_hra
    _add_hdhp_plan_to_wallet(wallet, current_hdhp_plan)

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_accounts"
    ) as mock_get_employee_accounts:
        mock_get_employee_accounts.return_value = (
            True,
            [
                {
                    "AccountType": "HRA",
                    "AnnualElection": 1400.00,
                    "AvailBalance": 0.00,
                    "PlanId": current_hdhp_plan.alegeus_plan_id,
                },
            ],
        )

        ytd_spend = enroll_wallet.get_alegeus_hdhp_plan_year_to_date_spend(wallet)
        assert ytd_spend == 140000


def test_get_alegeus_hdhp_plan_year_to_date_spend_missing_balances(
    qualified_alegeus_wallet_hra, current_hdhp_plan
):
    wallet = qualified_alegeus_wallet_hra
    _add_hdhp_plan_to_wallet(wallet, current_hdhp_plan)

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_accounts"
    ) as mock_get_employee_accounts, pytest.raises(ValueError):
        mock_get_employee_accounts.return_value = (
            True,
            [
                {
                    "AccountType": "HRA",
                    "PlanId": current_hdhp_plan.alegeus_plan_id,
                },
            ],
        )

        enroll_wallet.get_alegeus_hdhp_plan_year_to_date_spend(wallet)


def test_get_alegeus_hdhp_plan_year_to_date_spend_api_failure(
    qualified_alegeus_wallet_hra, current_hdhp_plan
):
    wallet = qualified_alegeus_wallet_hra
    _add_hdhp_plan_to_wallet(wallet, current_hdhp_plan)

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_accounts"
    ) as mock_get_employee_accounts, pytest.raises(ValueError):
        mock_get_employee_accounts.return_value = (False, None)

        enroll_wallet.get_alegeus_hdhp_plan_year_to_date_spend(wallet)


def test_update_employee_demographic__successful(
    qualified_alegeus_wallet_hra,
    qualified_wallet_enablement_hra,
    wallet_debitcardinator,
    factories,
    mock_e9y,
):
    mock_get_response = Response()
    mock_get_response.status_code = 200
    mock_get_response.json = lambda: {
        "BankName": "Test Checking",
        "BankAccountNumber": "0037308343",
        "BankAccountTypeCode": "1",
        "BankRoutingNumber": "064000017",
    }

    mock_put_response = Response()
    mock_put_response.status_code = 200
    mock_put_response.json = lambda: {}

    mock_e9y.grpc_service.wallet_enablement_by_user_id_search.return_value = (
        qualified_wallet_enablement_hra
    )

    api = enroll_wallet.AlegeusApi()
    wallet_debitcardinator(qualified_alegeus_wallet_hra)
    address = factories.AddressFactory(
        user=qualified_alegeus_wallet_hra.member, state="CA"
    )

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_details"
    ) as mock_get_request, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.put_employee_services_and_banking"
    ) as mock_put_request:
        mock_get_request.return_value = mock_get_response
        mock_put_request.return_value = mock_put_response

        was_successful = enroll_wallet.update_employee_demographic(
            api, qualified_alegeus_wallet_hra, address
        )

        assert was_successful is True
        assert mock_put_request.call_args.kwargs["member_address"] == address
        assert mock_put_request.call_args.kwargs["banking_info"] == {
            "BankAcctName": "Test Checking",
            "BankAccount": "0037308343",
            "BankAccountTypeCode": "1",
            "BankRoutingNumber": "064000017",
        }


def test_update_employee_demographic__successful_no_shipping_address(
    qualified_alegeus_wallet_hra,
    qualified_wallet_enablement_hra,
    wallet_debitcardinator,
    mock_e9y,
):
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}
    mock_e9y.grpc_service.wallet_enablement_by_user_id_search.return_value = (
        qualified_wallet_enablement_hra
    )

    mock_response_get_employee_details = Response()
    mock_response_get_employee_details.status_code = 200
    mock_response_get_employee_details.json = lambda: {}

    api = enroll_wallet.AlegeusApi()
    wallet_debitcardinator(qualified_alegeus_wallet_hra)

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.put_employee_services_and_banking"
    ) as mock_request, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_details"
    ) as mock_get_employee_details:
        mock_request.return_value = mock_response
        mock_get_employee_details.return_value = mock_response_get_employee_details
        was_successful = enroll_wallet.update_employee_demographic(
            api, qualified_alegeus_wallet_hra, None
        )

        assert was_successful is True
        assert mock_request.call_args.kwargs["member_address"] is None


def test_get_banking_info__api_failure(qualified_alegeus_wallet_hra):
    wallet = qualified_alegeus_wallet_hra

    mock_get_response = Response()
    mock_get_response.status_code = 500
    mock_get_response.json = lambda: {}

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_details"
    ) as mock_get_employee_details:
        mock_get_employee_details.return_value = mock_get_response

        banking_info = enroll_wallet.get_banking_info(api, wallet)
        assert banking_info is None


def test_get_banking_info__no_info(qualified_alegeus_wallet_hra):
    wallet = qualified_alegeus_wallet_hra

    mock_get_response = Response()
    mock_get_response.status_code = 200
    mock_get_response.json = lambda: {
        "BankName": "",
        "BankAccountNumber": "",
        "BankAccountTypeCode": "",
        "BankRoutingNumber": "",
    }

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_details"
    ) as mock_get_employee_details:
        mock_get_employee_details.return_value = mock_get_response

        banking_info = enroll_wallet.get_banking_info(api, wallet)
        assert banking_info is None


def test_get_banking_info__partial_info(qualified_alegeus_wallet_hra):
    wallet = qualified_alegeus_wallet_hra

    mock_get_response = Response()
    mock_get_response.status_code = 200
    mock_get_response.json = lambda: {
        "BankName": "",
        "BankAccountNumber": "",
        "BankAccountTypeCode": "",
        "BankRoutingNumber": "064000017",
    }

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_details"
    ) as mock_get_employee_details:
        mock_get_employee_details.return_value = mock_get_response

        banking_info = enroll_wallet.get_banking_info(api, wallet)
        assert banking_info is None


def test_get_banking_info__has_info(qualified_alegeus_wallet_hra):
    wallet = qualified_alegeus_wallet_hra

    mock_get_response = Response()
    mock_get_response.status_code = 200
    mock_get_response.json = lambda: {
        "BankName": "Test Checking",
        "BankAccountNumber": "0037308343",
        "BankAccountTypeCode": "1",
        "BankRoutingNumber": "064000017",
    }

    api = enroll_wallet.AlegeusApi()

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_details"
    ) as mock_get_employee_details:
        mock_get_employee_details.return_value = mock_get_response

        banking_info = enroll_wallet.get_banking_info(api, wallet)
        assert banking_info == {
            "BankAcctName": "Test Checking",
            "BankAccount": "0037308343",
            "BankAccountTypeCode": "1",
            "BankRoutingNumber": "064000017",
        }


def test_update_member_accounts_finds_plan__success(qualified_alegeus_wallet_hra):
    org_id = (
        qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization.id
    )
    # Set plan_start_date filter to grab any plans that start on or after this date.
    plan_start_date = datetime(year=2020, month=1, day=1).date()
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_account.return_value = True, []
        success = update_member_accounts(plan_start_date, [org_id])

    assert success is True
    assert mock_configure_account.called


@pytest.mark.parametrize(
    argnames=("category_currency", "category_amount", "rate", "usd_amount"),
    argvalues=[
        (None, 5_000, Decimal("1.00"), 5_000),
        ("USD", 5_000, Decimal("1.00"), 5_000),
        ("AUD", 5_000, Decimal("2.00"), 10_000),
        ("NZD", 5_000, Decimal("4.00"), 20_000),
    ],
)
def test_update_member_accounts_calls_configure_account_with_correct_usd_amount(
    enterprise_user: User,
    category_currency: str | None,
    category_amount: int,
    rate: Decimal,
    usd_amount: int,
):
    # Given
    org_settings = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id
    )
    plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="HRA"
        ),
        alegeus_plan_id="CHILDCARE",
        start_date=date(year=2020, month=1, day=3),
        end_date=date(year=2199, month=12, day=31),
        is_hdhp=False,
    )
    category = ReimbursementRequestCategoryFactory.create(
        label="childcare", reimbursement_plan=plan
    )
    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=category,
        reimbursement_request_category_maximum=category_amount,
        currency_code=category_currency,
    )
    currency_wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED,
        reimbursement_organization_settings=org_settings,
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=currency_wallet.id,
    )
    # Set plan_start_date filter to grab any plans that start on or after this date.
    plan_start_date = datetime(year=2020, month=1, day=1).date()
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_start_date",
        return_value=plan.start_date,
    ), patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account, patch(
        "wallet.repository.currency_fx_rate.CurrencyFxRateRepository.get_rate"
    ) as mock_get_rate:
        mock_get_rate.return_value = rate
        mock_configure_account.return_value = True, []

        # When
        update_member_accounts(plan_start_date, [enterprise_user.organization.id])

    # Then - check the amount called matches usd_amount expected
    mock_configure_account.assert_called_with(
        api=mock.ANY,
        wallet=mock.ANY,
        plan=mock.ANY,
        prefunded_amount=usd_amount,
        coverage_tier=mock.ANY,
        start_date=mock.ANY,
        messages=mock.ANY,
    )


def test_update_member_accounts_no_plan__success(qualified_alegeus_wallet_hra):
    # plan start date is 1 year after our mock plan date started
    plan_start_date = datetime(year=2021, month=1, day=1).date()
    org_id = (
        qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization.id
    )
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_account.return_value = True, []
        success = update_member_accounts(plan_start_date, [org_id])

    assert success is True
    assert mock_configure_account.call_count == 0


def test_update_member_accounts_org_settings_exception_no_org_found__fails():
    plan_start_date = datetime(year=2022, month=1, day=1).date()
    with pytest.raises(NoResultFound):
        update_member_accounts(plan_start_date, [1000])


def test_update_member_accounts_org_settings_exception_multi_orgs_found__fails(
    qualified_alegeus_wallet_hra,
):
    ReimbursementOrganizationSettingsFactory(
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization.id
    )
    plan_start_date = datetime(year=2022, month=1, day=1).date()
    with pytest.raises(MultipleResultsFound):
        update_member_accounts(
            plan_start_date,
            [
                qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization.id
            ],
        )


def test_update_member_accounts_alegeus_response_one_fails(
    qualified_alegeus_wallet_hra,
):
    # Even if one wallet fails we continue to process enrolling members

    user = factories.EnterpriseUserFactory.create()
    wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
    wallet.reimbursement_organization_settings = (
        qualified_alegeus_wallet_hra.reimbursement_organization_settings
    )
    factories.ReimbursementWalletUsersFactory.create(
        user_id=user.id,
        reimbursement_wallet_id=wallet.id,
    )

    org_id = (
        qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization.id
    )
    plan_start_date = datetime(year=2020, month=1, day=1).date()
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_account.return_value = False, []
        success = update_member_accounts(plan_start_date, [org_id])

    assert success is True
    assert mock_configure_account.call_count == 2


def test_update_member_accounts_alegeus_throws_exception(
    qualified_alegeus_wallet_hra,
):
    # Alegeus throws an Exception. Continue enrolling members.
    mock_response = Response()
    mock_response.status_code = 500
    mock_response.json = lambda: {}

    user = factories.EnterpriseUserFactory.create()
    wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
    factories.ReimbursementWalletUsersFactory.create(
        user_id=user.id,
        reimbursement_wallet_id=wallet.id,
    )
    wallet.reimbursement_organization_settings = (
        qualified_alegeus_wallet_hra.reimbursement_organization_settings
    )

    org_id = (
        qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization.id
    )
    plan_start_date = datetime(year=2020, month=1, day=1).date()
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_account.return_value = mock_response
        success = update_member_accounts(plan_start_date, [org_id])

    assert success is True
    assert mock_configure_account.call_count == 2


@pytest.mark.disable_auto_patch_configure_wallet
def test_configure_wallet_allowed_category__successful(
    qualified_wallet, category_associations_with_rules_and_settings
):
    mock_category = category_associations_with_rules_and_settings
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_account.return_value = True, []

        was_successful, messages = enroll_wallet.configure_wallet_allowed_category(
            wallet=qualified_wallet, allowed_category_id=mock_category.id
        )
        assert mock_configure_account.call_count == 1
        assert was_successful is True


@pytest.mark.disable_auto_patch_configure_wallet
def test_configure_wallet_allowed_category__fails(
    qualified_wallet, category_associations_with_rules_and_settings
):
    mock_category = category_associations_with_rules_and_settings
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_account.return_value = False, []

        was_successful, messages = enroll_wallet.configure_wallet_allowed_category(
            wallet=qualified_wallet, allowed_category_id=mock_category.id
        )
        assert mock_configure_account.call_count == 1
        assert was_successful is False


@pytest.mark.disable_auto_patch_configure_wallet
def test_configure_wallet_allowed_category__fails_exception(
    qualified_wallet, category_associations_with_rules_and_settings
):
    mock_category = category_associations_with_rules_and_settings
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_account.side_effect = Exception

        was_successful, messages = enroll_wallet.configure_wallet_allowed_category(
            wallet=qualified_wallet, allowed_category_id=mock_category.id
        )
        assert mock_configure_account.call_count == 1
        assert was_successful is False


@pytest.mark.disable_auto_patch_configure_wallet
def test_configure_wallet_allowed_category__fails_missing_category(
    qualified_wallet, category_associations_with_rules_and_settings
):
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        was_successful, messages = enroll_wallet.configure_wallet_allowed_category(
            wallet=qualified_wallet, allowed_category_id=99
        )
        assert mock_configure_account.call_count == 0
        assert was_successful is False


@pytest.mark.disable_auto_patch_configure_wallet
def test_configure_wallet_allowed_category__fails_missing_category_plan(
    qualified_wallet, category_associations_with_rules_and_settings
):
    category = ReimbursementRequestCategoryFactory.create(
        label="Preservation", reimbursement_plan=None
    )
    org_settings = qualified_wallet.reimbursement_organization_settings
    allowed_category = ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings_id=org_settings.id,
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=category,
        reimbursement_request_category_id=category.id,
        benefit_type=BenefitTypes.CURRENCY,
    )
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        was_successful, messages = enroll_wallet.configure_wallet_allowed_category(
            wallet=qualified_wallet, allowed_category_id=allowed_category.id
        )
        assert mock_configure_account.call_count == 0
        assert was_successful is True
