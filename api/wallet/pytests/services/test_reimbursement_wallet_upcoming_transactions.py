from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.billing.pytests.factories import BillFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from utils.random_string import generate_random_string
from wallet.models.constants import BenefitTypes
from wallet.resources.reimbursement_wallet_upcoming_transactions import (
    UserReimbursementWalletUpcomingTransactionsResource,
)


@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.ReimbursementWallet.get_direct_payment_balances"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource._wallet_or_404"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource._user_or_404"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource.user"
)
def test_no_wallet_benefit_type_found(
    mock_user_query,
    mock_user_or_404_query,
    mock_wallet_or_404_query,
    mock_get_direct_payment_balances,
    enterprise_user,
    wallet_with_pending_requests_no_claims,
):
    mock_user_query.return_value = enterprise_user
    mock_user_or_404_query.return_value = enterprise_user
    mock_wallet_or_404_query.return_value = wallet_with_pending_requests_no_claims
    mock_get_direct_payment_balances.return_value = (None, None, None)

    with pytest.raises(  # noqa  B017  TODO:  `assertRaises(Exception)` and `pytest.raises(Exception)` should be considered evil. They can lead to your test passing even if the code being tested is never executed due to a typo. Assert for a more specific exception (builtin or custom), or use `assertRaisesRegex` (if using `assertRaises`), or add the `match` keyword argument (if using `pytest.raises`), or use the context manager form with a target.
        Exception
    ):
        UserReimbursementWalletUpcomingTransactionsResource().get(123)


@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.ReimbursementWallet.get_direct_payment_balances"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource._wallet_or_404"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource._user_or_404"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource.user"
)
def test_no_procedures_found(
    mock_user_query,
    mock_user_or_404_query,
    mock_wallet_or_404_query,
    mock_get_direct_payment_balances,
    enterprise_user,
    wallet_with_pending_requests_no_claims,
):
    mock_user_query.return_value = enterprise_user
    mock_user_or_404_query.return_value = enterprise_user
    mock_wallet_or_404_query.return_value = wallet_with_pending_requests_no_claims
    mock_get_direct_payment_balances.return_value = (
        10000,
        10000,
        BenefitTypes.CURRENCY,
    )

    result, code = UserReimbursementWalletUpcomingTransactionsResource().get(123)

    assert code == 200
    assert result.get("offset") == 0
    assert result.get("limit") == 100
    assert result.get("total") == 0
    assert result.get("balance_after_upcoming_transactions") == ""
    assert len(result.get("upcoming")) == 0


@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.CostBreakdown.query"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.TreatmentProcedureRepository.get_all_treatments_from_wallet_id"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.ReimbursementWallet.get_direct_payment_balances"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource._wallet_or_404"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource._user_or_404"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource.user"
)
def test_scheduled_procedures_with_currency_wallet(
    mock_user_query,
    mock_user_or_404_query,
    mock_wallet_or_404_query,
    mock_get_direct_payment_balances,
    mock_treatment_procedures,
    mock_cost_breakdown_query,
    enterprise_user,
    wallet_with_pending_requests_no_claims,
):
    mock_user_query.return_value = enterprise_user
    mock_user_or_404_query.return_value = enterprise_user
    mock_wallet_or_404_query.return_value = wallet_with_pending_requests_no_claims
    mock_get_direct_payment_balances.return_value = (
        1000000,
        900000,
        BenefitTypes.CURRENCY,
    )

    procedure_name_one = generate_random_string(12, include_digit=False)
    procedure_name_two = generate_random_string(12, include_digit=False)

    mock_treatment_procedures.return_value = [
        # created at 12/27/2023
        TreatmentProcedureFactory.create(
            global_procedure_id="1",
            cost_breakdown_id=1,
            cost=2000,
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_name=procedure_name_one,
            created_at=datetime(2023, 12, 27, 23, 0),
        ),
        # created at 12/25/2023
        TreatmentProcedureFactory.create(
            global_procedure_id="2",
            cost_breakdown_id=2,
            cost=3000,
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_name=procedure_name_two,
            created_at=datetime(2023, 12, 25, 23, 0),
        ),
    ]
    mock_cost_breakdown_query.filter.return_value.all.return_value = [
        # created at 12/27/2023
        CostBreakdownFactory.create(
            id=1,
            total_employer_responsibility=1950,
            created_at=datetime(2023, 12, 27, 23, 0),
        ),
        # created at 12/25/2023
        CostBreakdownFactory.create(
            id=2,
            total_employer_responsibility=2800,
            created_at=datetime(2023, 12, 25, 23, 0),
        ),
    ]

    result, code = UserReimbursementWalletUpcomingTransactionsResource().get(123)

    assert code == 200
    assert result.get("offset") == 0
    assert result.get("limit") == 100
    assert result.get("total") == 2
    assert (
        result.get("balance_after_upcoming_transactions") == "$8,952.50"
    )  # $9000 - $19.5 - $28
    assert len(result.get("upcoming")) == 2

    first_result = result.get("upcoming")[0]
    # first_result points to the procedures whose corresponding cost breakdown is created on 12/25/2023
    assert first_result["maven_responsibility"] == "$28.00"
    assert first_result["procedure_name"] == procedure_name_two
    assert first_result["status"] == "NEW"
    assert first_result["bill_uuid"] == ""
    assert first_result["procedure_details"] == "Dec 25, 2023 | Covered by Maven"

    second_result = result.get("upcoming")[1]
    # second_result points to the procedures whose corresponding cost breakdown is created on 12/27/2023
    assert second_result["maven_responsibility"] == "$19.50"
    assert second_result["procedure_name"] == procedure_name_one
    assert second_result["status"] == "NEW"
    assert second_result["bill_uuid"] == ""
    assert second_result["procedure_details"] == "Dec 27, 2023 | Covered by Maven"


@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.CostBreakdown.query"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.TreatmentProcedureRepository.get_all_treatments_from_wallet_id"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.ReimbursementWallet.get_direct_payment_balances"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource._wallet_or_404"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource._user_or_404"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource.user"
)
def test_scheduled_procedures_with_cycle_wallet(
    mock_user_query,
    mock_user_or_404_query,
    mock_wallet_or_404_query,
    mock_get_direct_payment_balances,
    mock_treatment_procedures,
    mock_cost_breakdown_query,
    enterprise_user,
    wallet_with_pending_requests_no_claims,
):
    mock_user_query.return_value = enterprise_user
    mock_user_or_404_query.return_value = enterprise_user
    mock_wallet_or_404_query.return_value = wallet_with_pending_requests_no_claims
    mock_get_direct_payment_balances.return_value = (200, 180, BenefitTypes.CYCLE)

    procedure_name_one = generate_random_string(12, include_digit=False)
    procedure_name_two = generate_random_string(12, include_digit=False)

    mock_treatment_procedures.return_value = [
        # created at 12/27/2023
        TreatmentProcedureFactory.create(
            global_procedure_id="1",
            cost_breakdown_id=1,
            cost=2000,
            cost_credit=10,
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_name=procedure_name_one,
            created_at=datetime(2023, 12, 27, 23, 0),
        ),
        # created at 12/25/2023
        TreatmentProcedureFactory.create(
            global_procedure_id="2",
            cost_breakdown_id=2,
            cost=3000,
            cost_credit=15,
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_name=procedure_name_two,
            created_at=datetime(2023, 12, 25, 23, 0),
        ),
    ]
    mock_cost_breakdown_query.filter.return_value.all.return_value = [
        # created at 12/27/2023
        CostBreakdownFactory.create(
            id=1,
            total_employer_responsibility=1800,
            created_at=datetime(2023, 12, 27, 23, 0),
        ),
        # created at 12/25/2023
        CostBreakdownFactory.create(
            id=2,
            total_employer_responsibility=2800,
            created_at=datetime(2023, 12, 25, 23, 0),
        ),
    ]

    result, code = UserReimbursementWalletUpcomingTransactionsResource().get(123)

    assert code == 200
    assert result.get("offset") == 0
    assert result.get("limit") == 100
    assert result.get("total") == 2
    assert result.get("balance_after_upcoming_transactions") == "155 cycle credits"
    assert len(result.get("upcoming")) == 2

    first_result = result.get("upcoming")[0]
    # first_result points to the procedures whose corresponding cost breakdown is created on 12/25/2023
    assert first_result["maven_responsibility"] == "15 cycle credits"
    assert first_result["procedure_name"] == procedure_name_two
    assert first_result["status"] == "NEW"
    assert first_result["bill_uuid"] == ""
    assert first_result["procedure_details"] == "Dec 25, 2023 | Covered by Maven"

    second_result = result.get("upcoming")[1]
    # second_result points to the procedures whose corresponding cost breakdown is created on 12/27/2023
    assert second_result["maven_responsibility"] == "10 cycle credits"
    assert second_result["procedure_name"] == procedure_name_one
    assert second_result["status"] == "NEW"
    assert second_result["bill_uuid"] == ""
    assert second_result["procedure_details"] == "Dec 27, 2023 | Covered by Maven"


@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.BillingService.get_bills_by_procedure_ids"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.TreatmentProcedureRepository.get_all_treatments_from_wallet_id"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.ReimbursementWallet.get_direct_payment_balances"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource._wallet_or_404"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource._user_or_404"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource.user"
)
def test_complete_procedures_with_currency_wallet(
    mock_user_query,
    mock_user_or_404_query,
    mock_wallet_or_404_query,
    mock_get_direct_payment_balances,
    mock_treatment_procedures,
    mock_bill_service_query,
    enterprise_user,
    wallet_with_pending_requests_no_claims,
):
    mock_user_query.return_value = enterprise_user
    mock_user_or_404_query.return_value = enterprise_user
    mock_wallet_or_404_query.return_value = wallet_with_pending_requests_no_claims
    mock_get_direct_payment_balances.return_value = (
        1000000,
        900000,
        BenefitTypes.CURRENCY,
    )

    procedure_name_one = generate_random_string(12, include_digit=False)
    bill_uuid_one = str(uuid4())
    procedure_name_two = generate_random_string(12, include_digit=False)
    bill_uuid_two = str(uuid4())

    mock_treatment_procedures.return_value = [
        # created at 12/27/2023
        TreatmentProcedureFactory.create(
            id=1,
            global_procedure_id="1",
            cost_breakdown_id=1,
            cost=2000,
            status=TreatmentProcedureStatus.COMPLETED,
            procedure_name=procedure_name_one,
            created_at=datetime(2023, 12, 27, 23, 0),
        ),
        # created at 12/25/2023
        TreatmentProcedureFactory.create(
            id=2,
            global_procedure_id="2",
            cost_breakdown_id=2,
            cost=3000,
            status=TreatmentProcedureStatus.PARTIALLY_COMPLETED,
            procedure_name=procedure_name_two,
            created_at=datetime(2023, 12, 25, 23, 0),
        ),
    ]
    mock_bill_service_query.return_value = [
        # created at 12/27/2023
        BillFactory.create(
            procedure_id=1,
            uuid=bill_uuid_one,
            amount=1500,
            created_at=datetime(2023, 12, 27, 23, 0),
        ),
        # created at 12/25/2023
        BillFactory.create(
            procedure_id=2,
            uuid=bill_uuid_two,
            amount=2400,
            created_at=datetime(2023, 12, 25, 23, 0),
        ),
    ]

    result, code = UserReimbursementWalletUpcomingTransactionsResource().get(123)

    assert code == 200
    assert result.get("offset") == 0
    assert result.get("limit") == 100
    assert result.get("total") == 2
    # The balance is not affected by completed treatment procedure
    assert result.get("balance_after_upcoming_transactions") == "$9,000.00"
    assert len(result.get("upcoming")) == 2

    first_result = result.get("upcoming")[0]
    # first_result points to the procedures whose corresponding cost breakdown is created on 12/25/2023
    assert first_result["maven_responsibility"] == "$24.00"
    assert first_result["procedure_name"] == procedure_name_two
    assert first_result["status"] == "PROCESSING"
    assert first_result["bill_uuid"] == bill_uuid_two
    assert first_result["procedure_details"] == "Dec 25, 2023 | Covered by Maven"

    second_result = result.get("upcoming")[1]
    # second_result points to the procedures whose corresponding cost breakdown is created on 12/27/2023
    assert second_result["maven_responsibility"] == "$15.00"
    assert second_result["procedure_name"] == procedure_name_one
    assert second_result["status"] == "PROCESSING"
    assert second_result["bill_uuid"] == bill_uuid_one
    assert second_result["procedure_details"] == "Dec 27, 2023 | Covered by Maven"


@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.BillingService.get_bills_by_procedure_ids"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.TreatmentProcedureRepository.get_all_treatments_from_wallet_id"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.ReimbursementWallet.get_direct_payment_balances"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource._wallet_or_404"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource._user_or_404"
)
@patch(
    "wallet.resources.reimbursement_wallet_upcoming_transactions.UserReimbursementWalletUpcomingTransactionsResource.user"
)
def test_complete_procedures_with_cycle_wallet(
    mock_user_query,
    mock_user_or_404_query,
    mock_wallet_or_404_query,
    mock_get_direct_payment_balances,
    mock_treatment_procedures,
    mock_bill_service_query,
    enterprise_user,
    wallet_with_pending_requests_no_claims,
):
    mock_user_query.return_value = enterprise_user
    mock_user_or_404_query.return_value = enterprise_user
    mock_wallet_or_404_query.return_value = wallet_with_pending_requests_no_claims
    mock_get_direct_payment_balances.return_value = (
        200,
        180,
        BenefitTypes.CYCLE,
    )

    procedure_name_one = generate_random_string(12, include_digit=False)
    bill_uuid_one = str(uuid4())
    procedure_name_two = generate_random_string(12, include_digit=False)
    bill_uuid_two = str(uuid4())

    mock_treatment_procedures.return_value = [
        # created at 12/27/2023
        TreatmentProcedureFactory.create(
            id=1,
            global_procedure_id="1",
            cost_breakdown_id=1,
            cost=2000,
            cost_credit=10,
            status=TreatmentProcedureStatus.COMPLETED,
            procedure_name=procedure_name_one,
            created_at=datetime(2023, 12, 27, 23, 0),
        ),
        # created at 12/25/2023
        TreatmentProcedureFactory.create(
            id=2,
            global_procedure_id="2",
            cost_breakdown_id=2,
            cost=3000,
            cost_credit=15,
            status=TreatmentProcedureStatus.PARTIALLY_COMPLETED,
            procedure_name=procedure_name_two,
            created_at=datetime(2023, 12, 25, 23, 0),
        ),
    ]
    mock_bill_service_query.return_value = [
        # created at 12/27/2023
        BillFactory.create(
            procedure_id=1,
            uuid=bill_uuid_one,
            amount=1500,
            created_at=datetime(2023, 12, 27, 23, 0),
        ),
        # created at 12/25/2023
        BillFactory.create(
            procedure_id=2,
            uuid=bill_uuid_two,
            amount=2400,
            created_at=datetime(2023, 12, 25, 23, 0),
        ),
    ]

    result, code = UserReimbursementWalletUpcomingTransactionsResource().get(123)

    assert code == 200
    assert result.get("offset") == 0
    assert result.get("limit") == 100
    assert result.get("total") == 2
    # The balance is not affected by completed treatment procedure
    assert result.get("balance_after_upcoming_transactions") == "180 cycle credits"
    assert len(result.get("upcoming")) == 2

    first_result = result.get("upcoming")[0]
    # first_result points to the procedures whose corresponding cost breakdown is created on 12/25/2023
    assert first_result["maven_responsibility"] == "15 cycle credits"
    assert first_result["procedure_name"] == procedure_name_two
    assert first_result["status"] == "PROCESSING"
    assert first_result["bill_uuid"] == bill_uuid_two
    assert first_result["procedure_details"] == "Dec 25, 2023 | Covered by Maven"

    second_result = result.get("upcoming")[1]
    # second_result points to the procedures whose corresponding cost breakdown is created on 12/27/2023
    assert second_result["maven_responsibility"] == "10 cycle credits"
    assert second_result["procedure_name"] == procedure_name_one
    assert second_result["status"] == "PROCESSING"
    assert second_result["bill_uuid"] == bill_uuid_one
    assert second_result["procedure_details"] == "Dec 27, 2023 | Covered by Maven"
