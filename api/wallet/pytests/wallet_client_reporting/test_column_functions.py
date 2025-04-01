import datetime

import pytest

from eligibility.e9y import EligibilityVerification
from wallet.services.wallet_client_reporting import WALLET_REPORT_COLUMN_FUNCTIONS
from wallet.services.wallet_client_reporting_constants import ELIGIBILITY_SERVICE_COLS


@pytest.fixture
def eligibility_service_function(request):
    """
    Test all report column functions in the eligibility_service_cols list
    """
    function_name = request.param
    return WALLET_REPORT_COLUMN_FUNCTIONS[function_name]


@pytest.fixture
def eligibility_verification():
    return EligibilityVerification(
        date_of_birth=datetime.datetime(year=1990, month=12, day=1),
        first_name="Test Name",
        last_name="Test User",
        employer_assigned_id="mock_id",
        record={
            "lob": "mock_line_of_business",
            "payroll_dept": "mock_line_of_business",
        },
        user_id=0,
        organization_id=0,
        unique_corp_id="mock",
        dependent_id="mock",
        email="mock",
        verified_at=datetime.datetime.now(datetime.timezone.utc),
        created_at=datetime.datetime.now(datetime.timezone.utc),
        verification_type="mock",
        is_active=True,
    )


@pytest.mark.parametrize(
    "eligibility_service_function", ELIGIBILITY_SERVICE_COLS, indirect=True
)
def test_service_columns_with_verification(
    eligibility_service_function, eligibility_verification
):
    result = eligibility_service_function(eligibility_verification)
    assert result is not None
    assert result != ""


@pytest.mark.parametrize(
    "eligibility_service_function", ELIGIBILITY_SERVICE_COLS, indirect=True
)
def test_service_columns_without_verification(eligibility_service_function):
    result = eligibility_service_function(None)
    assert result == "" or result is None
