import pytest

from pytests.freezegun import freeze_time
from wallet.models.constants import ReimbursementRequestState
from wallet.pytests.factories import ReimbursementRequestFactory
from wallet.utils.common import (
    create_refund_reimbursement_request,
    has_tenure_exceeded,
    is_user_international,
)


@pytest.mark.parametrize(
    "start_date, days, years, expected",
    [
        # Cases based on 2024-10-24
        ("2023-10-24", 0, 1, True),  # Exactly one year has passed
        ("2023-10-25", 0, 1, False),  # 1 year has not passed yet
        ("2023-10-25", 366, 0, False),  # 365 days not yet passed
        ("2022-10-24", 700, 0, True),  # 700 days have passed
        ("2024-02-29", 0, 1, False),  # 1 year from Feb 29, 2024 (not yet)
        ("2024-10-24", 0, 0, True),  # 0 days or years should return True
        ("2024-10-24", -50, 0, True),  # negative days should return True
        ("2020-10-24", 0, 4, True),  # 4 years from 2020 has passed
        ("2021-10-25", 0, 3, False),  # 3 years not fully passed
        ("2022-10-25", 0, 2, False),  # 2 years not fully passed
    ],
)
@freeze_time("2024-10-24")
def test_has_tenure_exceeded(start_date, days, years, expected):
    result = has_tenure_exceeded(start_date=start_date, days=days, years=years)
    assert result == expected


@pytest.mark.parametrize(
    "e9y_record, user_country, expected",
    [
        # Case 1: work_country is non-US -> user is international
        ({"work_country": "CA"}, None, True),
        # Case 2: work_country is US -> user is not international
        ({"work_country": "US"}, None, False),
        # Case 3: work_country is missing, country is non-US -> user is international
        ({"country": "UK"}, None, True),
        # Case 4: work_country is missing, country is US -> user is not international
        ({"country": "US"}, None, False),
        # Case 5: Both work_country and country missing, user_country non-US -> user is international
        ({}, "FR", True),
        # Case 6: Both work_country and country missing, user_country is US -> user is not international
        ({}, "US", False),
        # Case 7: work_country is non-US, country is US -> prioritize work_country -> user is international
        ({"work_country": "CA", "country": "US"}, None, True),
        # Case 8: work_country is US, country is non-US -> prioritize work_country -> user is not international
        ({"work_country": "US", "country": "AU"}, None, False),
        # Case 9:  Both work_country is non-US, country is US -> user is international
        ({"work_country": "AU", "country": "AU"}, "US", True),
        # Case 10: Both e9y_record and user_country missing -> user is not international
        ({}, None, False),
    ],
)
def test_is_user_international(
    qualified_direct_payment_enabled_wallet,
    qualified_verification_hra,
    e9y_record,
    user_country,
    expected,
):
    qualified_verification_hra.record = e9y_record
    reimbursement_wallet = qualified_direct_payment_enabled_wallet
    reimbursement_wallet.member.member_profile.country_code = user_country
    user = reimbursement_wallet.employee_member

    result = is_user_international(qualified_verification_hra, user)
    # Assert
    assert result == expected


def test_create_refund_reimbursement_request(qualified_direct_payment_enabled_wallet):
    category = qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        1  # first is the default, second is the one created by pending_alegeus_wallet_hra
    ].reimbursement_request_category
    request = ReimbursementRequestFactory.create(
        wallet=qualified_direct_payment_enabled_wallet,
        category=category,
        state=ReimbursementRequestState.APPROVED,
        amount=100,
    )
    reversed = create_refund_reimbursement_request(
        original_request=request, refund_amount=100
    )
    assert reversed.amount == -100

    with pytest.raises(Exception, match="Refund amount must be greater than 0"):
        create_refund_reimbursement_request(
            original_request=request, refund_amount=-100
        )

    with pytest.raises(
        Exception, match="Cannot refund amount greater than original request amount"
    ):
        create_refund_reimbursement_request(original_request=request, refund_amount=200)
