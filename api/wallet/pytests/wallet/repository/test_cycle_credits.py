import pytest

from wallet.pytests.factories import (
    ReimbursementCycleMemberCreditTransactionFactory,
    ReimbursementRequestFactory,
)
from wallet.repository.cycle_credits import CycleCreditsRepository


@pytest.fixture
def cycle_credits_repository(session) -> CycleCreditsRepository:
    return CycleCreditsRepository(session)


@pytest.fixture(scope="function")
def reimbursement_for_cycle_wallet(wallet_cycle_based):
    category_association = wallet_cycle_based.get_or_create_wallet_allowed_categories[0]

    reimbursement = ReimbursementRequestFactory.create(
        reimbursement_request_category_id=category_association.reimbursement_request_category_id,
        wallet=wallet_cycle_based,
    )

    return reimbursement


@pytest.fixture(scope="function")
def credit_transaction_for_reimbursement(
    wallet_cycle_based, reimbursement_for_cycle_wallet
):
    credit_transaction = ReimbursementCycleMemberCreditTransactionFactory.create(
        reimbursement_request_id=reimbursement_for_cycle_wallet.id,
        reimbursement_cycle_credits=wallet_cycle_based.cycle_credits[0],
        amount=1,
    )
    return credit_transaction


def test_get_credit_transactions_for_reimbursement(
    cycle_credits_repository,
    reimbursement_for_cycle_wallet,
    credit_transaction_for_reimbursement,
):
    # Given

    # When
    credit_transactions = (
        cycle_credits_repository.get_credit_transactions_for_reimbursement(
            reimbursement_request_id=reimbursement_for_cycle_wallet.id
        )
    )

    assert credit_transactions[0] == credit_transaction_for_reimbursement


def test_get_credit_transactions_for_reimbursement_with_cycle_credit_filter(
    cycle_credits_repository,
    wallet_cycle_based,
    reimbursement_for_cycle_wallet,
    credit_transaction_for_reimbursement,
):
    # Given

    # When
    credit_transactions = (
        cycle_credits_repository.get_credit_transactions_for_reimbursement(
            reimbursement_request_id=reimbursement_for_cycle_wallet.id,
            cycle_credit_id=wallet_cycle_based.cycle_credits[0].id,
        )
    )

    assert credit_transactions[0] == credit_transaction_for_reimbursement


def test_get_credit_transactions_for_reimbursement_with_cycle_credit_filter_not_found(
    cycle_credits_repository,
    wallet_cycle_based,
    reimbursement_for_cycle_wallet,
    credit_transaction_for_reimbursement,
):
    # Given

    # When
    credit_transactions = (
        cycle_credits_repository.get_credit_transactions_for_reimbursement(
            reimbursement_request_id=reimbursement_for_cycle_wallet.id,
            cycle_credit_id=wallet_cycle_based.cycle_credits[0].id + 1,
        )
    )

    assert not credit_transactions


# Section: get_cycle_credit
def test_get_cycle_credits(cycle_credits_repository, wallet_cycle_based):
    # Given
    category_association = wallet_cycle_based.get_or_create_wallet_allowed_categories[0]

    # When
    cycle_credit = cycle_credits_repository.get_cycle_credit(
        reimbursement_wallet_id=wallet_cycle_based.id,
        category_association_id=category_association.id,
    )

    # Then
    assert cycle_credit


def test_get_cycle_credits_not_found(cycle_credits_repository, qualified_wallet):
    # Given
    category_association = qualified_wallet.get_or_create_wallet_allowed_categories[0]

    # When
    cycle_credit = cycle_credits_repository.get_cycle_credit(
        reimbursement_wallet_id=qualified_wallet.id,
        category_association_id=category_association.id,
    )

    # Then
    assert not cycle_credit


# Section: get_cycle_credit_by_category
def test_get_cycle_credits_by_category(cycle_credits_repository, wallet_cycle_based):
    # Given
    category = wallet_cycle_based.get_or_create_wallet_allowed_categories[
        0
    ].reimbursement_request_category

    # When
    cycle_credit = cycle_credits_repository.get_cycle_credit_by_category(
        reimbursement_wallet_id=wallet_cycle_based.id,
        category_id=category.id,
    )

    # Then
    assert cycle_credit
