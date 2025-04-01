import datetime

import pytest

from direct_payment.treatment_procedure.utils.procedure_utils import (
    calculate_benefits_expiration_date,
    get_currency_balance_from_credit_wallet_balance,
)


def test_get_currency_balance_from_credit_wallet_balance(
    treatment_procedure_cycle_based, wallet_cycle_based
):
    treatment_procedure_cycle_based.reimbursement_wallet_id = wallet_cycle_based.id

    wallet_balance = get_currency_balance_from_credit_wallet_balance(
        treatment_procedure_cycle_based
    )
    assert wallet_balance == 50000


def test_get_currency_balance_from_credit_wallet_balance__currency_wallet(
    treatment_procedure, wallet
):
    treatment_procedure.reimbursement_wallet_id = wallet.id

    wallet_balance = get_currency_balance_from_credit_wallet_balance(
        treatment_procedure
    )
    assert wallet_balance == 0


def test_get_currency_balance_from_credit_wallet_balance__zero_cost_credit(
    treatment_procedure_cycle_based, wallet_cycle_based
):
    treatment_procedure_cycle_based.reimbursement_wallet_id = wallet_cycle_based.id
    treatment_procedure_cycle_based.cost_credit = 0

    wallet_balance = get_currency_balance_from_credit_wallet_balance(
        treatment_procedure_cycle_based
    )
    assert wallet_balance == 50000


def test_get_currency_balance_from_credit_wallet_balance__zero_credits_remaining(
    treatment_procedure_cycle_based, wallet_cycle_based
):
    treatment_procedure_cycle_based.reimbursement_wallet_id = wallet_cycle_based.id
    wallet_cycle_based.cycle_credits[0].amount = 0

    wallet_balance = get_currency_balance_from_credit_wallet_balance(
        treatment_procedure_cycle_based
    )
    assert wallet_balance == 0.0


def test_get_currency_balance_from_credit_wallet_balance__zero_credits_remaining_and_zero_cost_credit(
    treatment_procedure_cycle_based, wallet_cycle_based
):
    treatment_procedure_cycle_based.reimbursement_wallet_id = wallet_cycle_based.id
    treatment_procedure_cycle_based.cost_credit = 0
    wallet_cycle_based.cycle_credits[0].amount = 0

    wallet_balance = get_currency_balance_from_credit_wallet_balance(
        treatment_procedure_cycle_based
    )
    assert wallet_balance == 50000


def test_get_currency_balance_from_credit_wallet_balance__partial_credits_remaining(
    treatment_procedure_cycle_based, wallet_cycle_based
):
    treatment_procedure_cycle_based.reimbursement_wallet_id = wallet_cycle_based.id
    wallet_cycle_based.cycle_credits[0].amount = 4

    wallet_balance = get_currency_balance_from_credit_wallet_balance(
        treatment_procedure_cycle_based
    )
    assert wallet_balance == 40000.0


@pytest.mark.parametrize(
    "end_date, expected_expiration_date",
    [
        (datetime.date(2024, 5, 15), datetime.date(2024, 6, 1)),  # Middle of the month
        (datetime.date(2024, 5, 31), datetime.date(2024, 6, 1)),  # End of the month
        (
            datetime.date(2024, 5, 1),
            datetime.date(2024, 6, 1),
        ),  # Beginning of the month
        (
            datetime.date(2024, 12, 31),
            datetime.date(2025, 1, 1),
        ),  # Last day of December
    ],
)
def test_calculate_benefits_expiration_date(end_date, expected_expiration_date):
    assert calculate_benefits_expiration_date(end_date) == expected_expiration_date
