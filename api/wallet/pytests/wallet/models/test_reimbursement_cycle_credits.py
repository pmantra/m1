import pytest

from pytests.common.global_procedures.factories import GlobalProcedureFactory
from wallet.models.constants import ReimbursementRequestType
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.models.reimbursement_wallet_credit_transaction import (
    ReimbursementCycleMemberCreditTransaction,
)
from wallet.pytests.factories import ReimbursementCycleMemberCreditTransactionFactory


class TestReimbursementCycleCredits:
    def test_deduct_full_credits(self, cycle_benefits_wallet):
        gp_cost = 3
        wallet = cycle_benefits_wallet
        reimbursement = wallet.reimbursement_requests[0]
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        wallet_credits = ReimbursementCycleCredits.query.filter_by(
            reimbursement_wallet_id=wallet.id,
            reimbursement_organization_settings_allowed_category_id=category.id,
        ).first()
        global_procedure = GlobalProcedureFactory(credits=gp_cost)
        result = wallet_credits.deduct_credits_for_reimbursement_and_procedure(
            reimbursement, global_procedure, gp_cost
        )
        assert result == 36 - gp_cost
        assert wallet_credits.amount == result
        assert len(wallet_credits.transactions) == 2
        new_transaction = wallet_credits.transactions[1]
        assert new_transaction.amount == gp_cost * -1
        assert new_transaction.reimbursement_request_id == reimbursement.id

    def test_deduct_partial_credits(self, cycle_benefits_wallet):
        # Balance doesn't have enough credits, but will subtract what they have left
        gp_cost = 40
        wallet = cycle_benefits_wallet
        reimbursement = wallet.reimbursement_requests[0]
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        wallet_credits = ReimbursementCycleCredits.query.filter_by(
            reimbursement_wallet_id=wallet.id,
            reimbursement_organization_settings_allowed_category_id=category.id,
        ).first()
        credit_balance = wallet_credits.amount
        global_procedure = GlobalProcedureFactory(credits=gp_cost)
        result = wallet_credits.deduct_credits_for_reimbursement_and_procedure(
            reimbursement, global_procedure, gp_cost
        )
        assert result == 0
        assert wallet_credits.amount == result
        new_transaction = wallet_credits.transactions[1]
        assert new_transaction.amount == credit_balance * -1

    def test_add_back_credits(self, cycle_benefits_wallet):
        wallet = cycle_benefits_wallet
        reimbursement = wallet.reimbursement_requests[0]
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        wallet_credits = ReimbursementCycleCredits.query.filter_by(
            reimbursement_wallet_id=wallet.id,
            reimbursement_organization_settings_allowed_category_id=category.id,
        ).first()
        result = wallet_credits.add_back_credits_for_reimbursement_and_procedure(
            reimbursement
        )
        assert result == 72
        assert wallet_credits.amount == result
        new_transaction = wallet_credits.transactions[1]
        assert new_transaction.amount == 36

    def test_add_back_credits_already_refunded(self, cycle_benefits_wallet):
        wallet = cycle_benefits_wallet
        reimbursement = wallet.reimbursement_requests[0]
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        wallet_credits = ReimbursementCycleCredits.query.filter_by(
            reimbursement_wallet_id=wallet.id,
            reimbursement_organization_settings_allowed_category_id=category.id,
        ).first()
        ReimbursementCycleMemberCreditTransactionFactory.create(
            reimbursement_cycle_credits_id=wallet_credits.id,
            amount=36,
            notes="Refund",
            reimbursement_request_id=reimbursement.id,
        )
        with pytest.raises(ValueError):
            wallet_credits.add_back_credits_for_reimbursement_and_procedure(
                reimbursement
            )

    def test_add_back_credits_zero_amount(self, cycle_benefits_wallet):
        wallet = cycle_benefits_wallet
        reimbursement = wallet.reimbursement_requests[0]
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        wallet_credits = ReimbursementCycleCredits.query.filter_by(
            reimbursement_wallet_id=wallet.id,
            reimbursement_organization_settings_allowed_category_id=category.id,
        ).first()
        transaction = ReimbursementCycleMemberCreditTransaction.query.first()
        transaction.amount = 0
        amount = wallet_credits.add_back_credits_for_reimbursement_and_procedure(
            reimbursement
        )
        assert amount == 36

    def test_deduct_credits_for_manual_reimbursement(self, cycle_benefits_wallet):
        credit_cost = 3
        wallet = cycle_benefits_wallet
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )

        reimbursement = wallet.reimbursement_requests[0]
        reimbursement.reimbursement_type = ReimbursementRequestType.MANUAL
        reimbursement.cost_credit = credit_cost

        wallet_credits = ReimbursementCycleCredits.query.filter_by(
            reimbursement_wallet_id=wallet.id,
            reimbursement_organization_settings_allowed_category_id=category.id,
        ).first()

        result = wallet_credits.deduct_credits_for_manual_reimbursement(reimbursement)
        assert result == 36 - credit_cost
        assert wallet_credits.amount == result
        assert len(wallet_credits.transactions) == 2
        new_transaction = wallet_credits.transactions[1]
        assert new_transaction.amount == credit_cost * -1
        assert new_transaction.reimbursement_request_id == reimbursement.id
