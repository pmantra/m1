from unittest import mock
from unittest.mock import MagicMock

import pytest
from requests import Response

from cost_breakdown.constants import ClaimType
from cost_breakdown.pytests.factories import ReimbursementRequestToCostBreakdownFactory
from pytests.common.global_procedures.factories import GlobalProcedureFactory
from wallet.constants import NUM_CREDITS_PER_CYCLE
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.models.reimbursement_wallet_credit_transaction import (
    ReimbursementCycleMemberCreditTransaction,
)
from wallet.pytests.factories import (
    ReimbursementAccountFactory,
    ReimbursementCycleCreditsFactory,
)
from wallet.services.reimbursement_wallet_benefit_type_converter import (
    BenefitTypeConversionError,
    BenefitTypeConversionValidationError,
    ReimbursementWalletBenefitTypeConverter,
)

##### Section: Fixtures


@pytest.fixture(scope="function")
def benefit_type_converter(session) -> ReimbursementWalletBenefitTypeConverter:
    with mock.patch(
        "common.global_procedures.procedure.ProcedureService", autospec=True
    ) as mock_procedure:
        yield ReimbursementWalletBenefitTypeConverter(
            session=session, procedure_service=mock_procedure, alegeus_api=MagicMock()
        )


@pytest.fixture(scope="function")
def successful_alegeus_response() -> MagicMock:
    mock_success_response = MagicMock(spec=Response)
    mock_success_response.status_code = 200
    return mock_success_response


@pytest.fixture(scope="function")
def failed_alegeus_response() -> MagicMock:
    mock_failed_response = MagicMock(spec=Response)
    mock_failed_response.status_code = 500
    return mock_failed_response


class TestConvertReimbursementToCurrency:
    @staticmethod
    def test_convert_reimbursement_to_currency(
        cycle_based_reimbursed_reimbursement, currency_based_category_association
    ):
        """
        Tests that the following updates are made to the reimbursement request
        1. reimbursement_request_category_id is assigned to the new currency based category
        """
        # When
        ReimbursementWalletBenefitTypeConverter.convert_reimbursement_to_currency(
            reimbursement_request=cycle_based_reimbursed_reimbursement,
            new_category=currency_based_category_association,
        )

        # Then
        # 1. New category is assigned to the reimbursement
        assert (
            cycle_based_reimbursed_reimbursement.reimbursement_request_category_id
            == currency_based_category_association.reimbursement_request_category_id
        )

    @staticmethod
    def test_convert_reimbursement_to_currency_invalid_category(
        cycle_based_reimbursed_reimbursement, cycle_based_category_association
    ):
        """Test that if the new_category is not a currency category, we raise an exception"""
        # When - Then
        with pytest.raises(
            BenefitTypeConversionValidationError,
            match=f"new_category is not of 'CURRENCY' type: category association id: {str(cycle_based_category_association.id)}",
        ):
            ReimbursementWalletBenefitTypeConverter.convert_reimbursement_to_currency(
                reimbursement_request=cycle_based_reimbursed_reimbursement,
                new_category=cycle_based_category_association,
            )


class TestConvertCycleToCurrency:
    @staticmethod
    def test_convert_cycle_to_currency_invalid_cycle_category(
        benefit_type_converter,
        wallet_cycle_based,
        cycle_based_category_association,
        currency_based_category_association,
    ):
        """Test that if the cycle_category is not a cycle category, we raise an exception"""
        # When - Then
        with pytest.raises(
            BenefitTypeConversionValidationError,
            match="cycle_category is not of 'CYCLE' type",
        ):
            benefit_type_converter.convert_cycle_to_currency(
                wallet=wallet_cycle_based,
                cycle_category=currency_based_category_association,
                currency_category=currency_based_category_association,
            )

    @staticmethod
    def test_convert_cycle_to_currency_invalid_currency_category(
        benefit_type_converter,
        wallet_cycle_based,
        cycle_based_category_association,
        currency_based_category_association,
    ):
        """Test that if the currency_category is not a currency category, we raise an exception"""
        # When - Then
        with pytest.raises(
            BenefitTypeConversionValidationError,
            match="currency_category is not of 'CURRENCY' type",
        ):
            benefit_type_converter.convert_cycle_to_currency(
                wallet=wallet_cycle_based,
                cycle_category=cycle_based_category_association,
                currency_category=cycle_based_category_association,
            )

    @staticmethod
    def test_convert_cycle_to_currency_single_reimbursed_reimbursement(
        benefit_type_converter,
        wallet_cycle_based,
        cycle_based_reimbursed_reimbursement,
        cycle_based_category_association,
        currency_based_category_association,
    ):
        """
        Test that the following conditions are met when we run convert_cycle_to_currency()
            1. New currency based category is assigned to the reimbursement request
            2. The amount of the REIMBURSED reimbursement is returned as part of the the total spend
        """
        # Given
        assert (
            cycle_based_reimbursed_reimbursement.reimbursement_request_category_id
            == cycle_based_category_association.reimbursement_request_category_id
        )

        # When
        usd_spend: int = benefit_type_converter.convert_cycle_to_currency(
            wallet=wallet_cycle_based,
            cycle_category=cycle_based_category_association,
            currency_category=currency_based_category_association,
        )

        # Then
        assert (
            cycle_based_reimbursed_reimbursement.reimbursement_request_category_id
            == currency_based_category_association.reimbursement_request_category_id
        )
        assert usd_spend == 1_000_00

    @staticmethod
    def test_convert_cycle_to_currency_single_pending_reimbursement(
        benefit_type_converter,
        wallet_cycle_based,
        cycle_based_pending_reimbursement,
        cycle_based_category_association,
        currency_based_category_association,
    ):
        """
        Test that the following conditions are met when we run convert_cycle_to_currency()
            1. New currency based category is assigned to the reimbursement request
            2. 0 is returned since the reimbursement is PENDING
        """
        # Given
        assert (
            cycle_based_pending_reimbursement.reimbursement_request_category_id
            == cycle_based_category_association.reimbursement_request_category_id
        )

        # When
        usd_spend: int = benefit_type_converter.convert_cycle_to_currency(
            wallet=wallet_cycle_based,
            cycle_category=cycle_based_category_association,
            currency_category=currency_based_category_association,
        )

        # Then
        assert (
            cycle_based_pending_reimbursement.reimbursement_request_category_id
            == currency_based_category_association.reimbursement_request_category_id
        )
        assert usd_spend == 0

    @staticmethod
    def test_convert_cycle_to_currency_no_reimbursements(
        benefit_type_converter,
        wallet_cycle_based,
        cycle_based_category_association,
        currency_based_category_association,
    ):
        """
        Test that the following conditions are met when we run convert_cycle_to_currency()
            1. 0 is returned since there are no reimbursements
        """
        # When
        usd_spend: int = benefit_type_converter.convert_cycle_to_currency(
            wallet=wallet_cycle_based,
            cycle_category=cycle_based_category_association,
            currency_category=currency_based_category_association,
        )

        # Then
        assert usd_spend == 0


class TestConvertReimbursementToCycle:
    @staticmethod
    def test_convert_reimbursement_to_cycle_with_cost_credit(
        session,
        benefit_type_converter,
        wallet_currency_based,
        currency_based_reimbursed_reimbursement,
        currency_based_category_association,
        cycle_based_category_association,
    ):
        """
        This test case is for reimbursement request
        1. With cost_credit populated
        2. No prior ReimbursementCycleMemberCreditTransaction attached to reimbursement request

        Assert the following
        1. The credit transaction was created
        2. The new cycle based category was created
        3. The CycleCredit balance is correctly updated
        4. The cost_credit on the reimbursement is set
        """
        # Given
        starting_balance: int = (
            cycle_based_category_association.num_cycles * NUM_CREDITS_PER_CYCLE
        )
        cycle_credit = ReimbursementCycleCreditsFactory.create(
            reimbursement_wallet_id=wallet_currency_based.id,
            reimbursement_organization_settings_allowed_category_id=cycle_based_category_association.id,
            amount=starting_balance,
        )
        currency_based_reimbursed_reimbursement.cost_credit = 2

        # When
        benefit_type_converter.convert_reimbursement_to_cycle(
            reimbursement_request=currency_based_reimbursed_reimbursement,
            new_category=cycle_based_category_association,
            cycle_credit=cycle_credit,
        )

        # Then
        credit_trans = (
            session.query(ReimbursementCycleMemberCreditTransaction)
            .filter(
                ReimbursementCycleMemberCreditTransaction.reimbursement_request_id
                == currency_based_reimbursed_reimbursement.id
            )
            .one_or_none()
        )
        # 1. New category is assigned to the reimbursement
        assert (
            currency_based_reimbursed_reimbursement.reimbursement_request_category_id
            == cycle_based_category_association.reimbursement_request_category_id
        )
        # 2. New ReimbursementCycleMemberCreditTransaction added
        assert credit_trans.amount == -2
        # 3. CycleCredit is updated
        assert cycle_credit.amount == (starting_balance - 2)
        # 4. cost_credit is updated
        assert currency_based_reimbursed_reimbursement.cost_credit == 2

    @staticmethod
    def test_convert_reimbursement_to_cycle_with_cost_credit_for_non_terminal_manual_reimbursement(
        session,
        benefit_type_converter,
        wallet_currency_based,
        currency_based_pending_reimbursement,
        currency_based_category_association,
        cycle_based_category_association,
    ):
        """
        This test case is for reimbursement request
        1. Without cost_credit populated
        2. No prior ReimbursementCycleMemberCreditTransaction attached to reimbursement request

        Assert the following
        1. The credit transaction was NOT created
        2. The new cycle based category was assigned
        3. The CycleCredit balance is NOT updated
        4. The cost_credit on the reimbursement is set
        """
        # Given
        starting_balance: int = (
            cycle_based_category_association.num_cycles * NUM_CREDITS_PER_CYCLE
        )
        cycle_credit = ReimbursementCycleCreditsFactory.create(
            reimbursement_wallet_id=wallet_currency_based.id,
            reimbursement_organization_settings_allowed_category_id=cycle_based_category_association.id,
            amount=starting_balance,
        )
        currency_based_pending_reimbursement.cost_credit = 2

        # When
        benefit_type_converter.convert_reimbursement_to_cycle(
            reimbursement_request=currency_based_pending_reimbursement,
            new_category=cycle_based_category_association,
            cycle_credit=cycle_credit,
        )

        # Then
        credit_trans = (
            session.query(ReimbursementCycleMemberCreditTransaction)
            .filter(
                ReimbursementCycleMemberCreditTransaction.reimbursement_request_id
                == currency_based_pending_reimbursement.id
            )
            .one_or_none()
        )
        # 1. New category is assigned to the reimbursement
        assert (
            currency_based_pending_reimbursement.reimbursement_request_category_id
            == cycle_based_category_association.reimbursement_request_category_id
        )
        # 2. New ReimbursementCycleMemberCreditTransaction added
        assert not credit_trans
        # 3. CycleCredit is not updated
        assert cycle_credit.amount == starting_balance
        # 4. cost_credit is updated
        assert currency_based_pending_reimbursement.cost_credit == 2

    @staticmethod
    def test_convert_reimbursement_to_cycle_with_cost_credit_balance_less_than_zero(
        session,
        benefit_type_converter,
        wallet_currency_based,
        currency_based_reimbursed_reimbursement,
        currency_based_category_association,
        cycle_based_category_association,
    ):
        """
        This test case is for reimbursement request
        1. With cost_credit populated
        2. No prior ReimbursementCycleMemberCreditTransaction attached to reimbursement request
        3. The balance is reduced to below 0

        Assert the following
        1. The credit transaction was created
        2. The new cycle based category was created
        3. The CycleCredit balance is updated but not below 0
        """
        # Given
        starting_balance: int = (
            cycle_based_category_association.num_cycles * NUM_CREDITS_PER_CYCLE
        )
        cycle_credit = ReimbursementCycleCreditsFactory.create(
            reimbursement_wallet_id=wallet_currency_based.id,
            reimbursement_organization_settings_allowed_category_id=cycle_based_category_association.id,
            amount=starting_balance,
        )
        currency_based_reimbursed_reimbursement.cost_credit = 200

        # When
        benefit_type_converter.convert_reimbursement_to_cycle(
            reimbursement_request=currency_based_reimbursed_reimbursement,
            new_category=cycle_based_category_association,
            cycle_credit=cycle_credit,
        )

        # Then
        credit_trans = (
            session.query(ReimbursementCycleMemberCreditTransaction)
            .filter(
                ReimbursementCycleMemberCreditTransaction.reimbursement_request_id
                == currency_based_reimbursed_reimbursement.id
            )
            .one_or_none()
        )
        # 1. New category is assigned to the reimbursement
        assert (
            currency_based_reimbursed_reimbursement.reimbursement_request_category_id
            == cycle_based_category_association.reimbursement_request_category_id
        )
        # 2. New ReimbursementCycleMemberCreditTransaction added
        assert credit_trans.amount == -200
        # 3. CycleCredit is updated
        assert cycle_credit.amount == 0

    @staticmethod
    def test_convert_reimbursement_to_cycle_for_direct_payment_employer_reimbursement(
        session,
        benefit_type_converter,
        wallet_currency_based,
        dp_employer_currency_based_reimbursed_reimbursement,
        currency_based_scheduled_treatment_procedure,
        currency_based_category_association,
        cycle_based_category_association,
    ):
        """
        This test case is for EMPLOYER reimbursement requests created by CB

        Assert the following
        1. The credit transaction was created
        2. The new cycle based category was created
        3. The CycleCredit balance is correctly updated
        """
        # Given
        starting_balance: int = (
            cycle_based_category_association.num_cycles * NUM_CREDITS_PER_CYCLE
        )
        cycle_credit = ReimbursementCycleCreditsFactory.create(
            reimbursement_wallet_id=wallet_currency_based.id,
            reimbursement_organization_settings_allowed_category_id=cycle_based_category_association.id,
            amount=starting_balance,
        )
        dp_employer_currency_based_reimbursed_reimbursement.cost_credit = None
        benefit_type_converter.procedure_service.get_procedure_by_id.return_value = (
            GlobalProcedureFactory.create(credits=2)
        )
        assert currency_based_scheduled_treatment_procedure.cost_credit is None

        # When
        benefit_type_converter.convert_reimbursement_to_cycle(
            reimbursement_request=dp_employer_currency_based_reimbursed_reimbursement,
            new_category=cycle_based_category_association,
            cycle_credit=cycle_credit,
        )

        # Then
        credit_trans = (
            session.query(ReimbursementCycleMemberCreditTransaction)
            .filter(
                ReimbursementCycleMemberCreditTransaction.reimbursement_request_id
                == dp_employer_currency_based_reimbursed_reimbursement.id
            )
            .one_or_none()
        )
        # 1. New category is assigned to the reimbursement
        assert (
            dp_employer_currency_based_reimbursed_reimbursement.reimbursement_request_category_id
            == cycle_based_category_association.reimbursement_request_category_id
        )
        # 2. New ReimbursementCycleMemberCreditTransaction added
        assert credit_trans.amount == -2
        # 3. The CycleCredit balance is correctly updated
        assert cycle_credit.amount == (starting_balance - 2)

    @staticmethod
    def test_convert_reimbursement_to_cycle_for_direct_payment_employee_reimbursement(
        session,
        benefit_type_converter,
        wallet_currency_based,
        dp_employee_currency_based_reimbursed_reimbursement,
        currency_based_category_association,
        cycle_based_category_association,
    ):
        """
        This test case is for EMPLOYEE reimbursement requests created by CB

        Assert the following
        1. The new cycle based category was assigned
        2. No cycle credit transaction was created
        """
        # Given
        starting_balance: int = (
            cycle_based_category_association.num_cycles * NUM_CREDITS_PER_CYCLE
        )
        cycle_credit = ReimbursementCycleCreditsFactory.create(
            reimbursement_wallet_id=wallet_currency_based.id,
            reimbursement_organization_settings_allowed_category_id=cycle_based_category_association.id,
            amount=starting_balance,
        )

        # When
        benefit_type_converter.convert_reimbursement_to_cycle(
            reimbursement_request=dp_employee_currency_based_reimbursed_reimbursement,
            new_category=cycle_based_category_association,
            cycle_credit=cycle_credit,
        )

        # Then
        credit_trans = (
            session.query(ReimbursementCycleMemberCreditTransaction)
            .filter(
                ReimbursementCycleMemberCreditTransaction.reimbursement_request_id
                == dp_employee_currency_based_reimbursed_reimbursement.id
            )
            .one_or_none()
        )
        # 1. New category is assigned to the reimbursement
        assert (
            dp_employee_currency_based_reimbursed_reimbursement.reimbursement_request_category_id
            == cycle_based_category_association.reimbursement_request_category_id
        )
        # 2. No cycle credit transaction was created
        assert not credit_trans

    @staticmethod
    def test_convert_reimbursement_to_cycle_with_no_cost_credit_missing_expense_subtype(
        session,
        benefit_type_converter,
        wallet_currency_based,
        currency_based_reimbursed_reimbursement,
        currency_based_category_association,
        cycle_based_category_association,
    ):
        """
        This test case is for reimbursement request (for non-reimbursements that are not approved/reimbursed)
        1. Without cost_credit populated
        2. No prior ReimbursementCycleMemberCreditTransaction attached to reimbursement request
        3. ReimbursementRequest is missing wallet_expense_subtype

        Assert the following
        1. The category is set to the new category
        2. No credit transaction was created
        """
        # Given
        cycle_credit = ReimbursementCycleCreditsFactory.create(
            reimbursement_wallet_id=wallet_currency_based.id,
            reimbursement_organization_settings_allowed_category_id=cycle_based_category_association.id,
            amount=cycle_based_category_association.num_cycles * NUM_CREDITS_PER_CYCLE,
        )
        currency_based_reimbursed_reimbursement.cost_credit = None
        currency_based_reimbursed_reimbursement.wallet_expense_subtype = None

        # When
        reimbursement = benefit_type_converter.convert_reimbursement_to_cycle(
            reimbursement_request=currency_based_reimbursed_reimbursement,
            new_category=cycle_based_category_association,
            cycle_credit=cycle_credit,
        )

        # Then
        credit_trans = (
            session.query(ReimbursementCycleMemberCreditTransaction)
            .filter(
                ReimbursementCycleMemberCreditTransaction.reimbursement_request_id
                == currency_based_reimbursed_reimbursement.id
            )
            .one_or_none()
        )
        assert (
            reimbursement.reimbursement_request_category_id
            == cycle_based_category_association.reimbursement_request_category_id
        )
        assert not credit_trans

    @staticmethod
    def test_convert_reimbursement_to_cycle_for_direct_payment_employer_reimbursement_no_treatment_procedures_found(
        session,
        benefit_type_converter,
        wallet_currency_based,
        dp_currency_based_reimbursed_reimbursement,
        currency_based_category_association,
        cycle_based_category_association,
        currency_based_cost_breakdown,
    ):
        """
        This test case is for EMPLOYER reimbursement requests created by CB, but no TP could be found

        Assert the following
        1. An exception is raised
        """
        # Given
        starting_balance: int = (
            cycle_based_category_association.num_cycles * NUM_CREDITS_PER_CYCLE
        )
        cycle_credit = ReimbursementCycleCreditsFactory.create(
            reimbursement_wallet_id=wallet_currency_based.id,
            reimbursement_organization_settings_allowed_category_id=cycle_based_category_association.id,
            amount=starting_balance,
        )
        ReimbursementRequestToCostBreakdownFactory.create(
            reimbursement_request_id=dp_currency_based_reimbursed_reimbursement.id,
            treatment_procedure_uuid="bahh",
            cost_breakdown_id=currency_based_cost_breakdown.id,
            claim_type=ClaimType.EMPLOYER,
        )

        # When
        with pytest.raises(
            BenefitTypeConversionError,
            match="Not able to find TreatmentProcedure for reimbursement request",
        ):
            benefit_type_converter.convert_reimbursement_to_cycle(
                reimbursement_request=dp_currency_based_reimbursed_reimbursement,
                new_category=cycle_based_category_association,
                cycle_credit=cycle_credit,
            )

    @staticmethod
    def test_convert_reimbursement_to_cycle_with_no_cost_credit_expense_subtype_missing_gp_id(
        session,
        benefit_type_converter,
        wallet_currency_based,
        currency_based_reimbursed_reimbursement,
        currency_based_category_association,
        cycle_based_category_association,
    ):
        """
        This test case is for reimbursement request (This is for non-medical expenses)
        1. Without cost_credit populated
        2. No prior ReimbursementCycleMemberCreditTransaction attached to reimbursement request
        3. ReimbursementRequest.wallet_expense_subtype is missing global_procedure_id

        Assert the following
        1. The category is set to the new category
        2. No credit transaction was created
        """
        # Given
        cycle_credit = ReimbursementCycleCreditsFactory.create(
            reimbursement_wallet_id=wallet_currency_based.id,
            reimbursement_organization_settings_allowed_category_id=cycle_based_category_association.id,
            amount=cycle_based_category_association.num_cycles * NUM_CREDITS_PER_CYCLE,
        )
        currency_based_reimbursed_reimbursement.cost_credit = None
        currency_based_reimbursed_reimbursement.wallet_expense_subtype.global_procedure_id = (
            None
        )

        # When
        reimbursement = benefit_type_converter.convert_reimbursement_to_cycle(
            reimbursement_request=currency_based_reimbursed_reimbursement,
            new_category=cycle_based_category_association,
            cycle_credit=cycle_credit,
        )

        # Then
        credit_trans = (
            session.query(ReimbursementCycleMemberCreditTransaction)
            .filter(
                ReimbursementCycleMemberCreditTransaction.reimbursement_request_id
                == currency_based_reimbursed_reimbursement.id
            )
            .one_or_none()
        )
        assert (
            reimbursement.reimbursement_request_category_id
            == cycle_based_category_association.reimbursement_request_category_id
        )
        assert not credit_trans

    @staticmethod
    def test_convert_reimbursement_to_cycle_with_no_cost_credit_global_procedure_not_found(
        session,
        benefit_type_converter,
        wallet_currency_based,
        currency_based_reimbursed_reimbursement,
        currency_based_category_association,
        cycle_based_category_association,
    ):
        """
        This test case is for reimbursement request
        1. Without cost_credit populated
        2. No prior ReimbursementCycleMemberCreditTransaction attached to reimbursement request
        3. GlobalProcedure is not found

        Assert the following
        1. An exception is raised
        """
        # Given
        cycle_credit = ReimbursementCycleCreditsFactory.create(
            reimbursement_wallet_id=wallet_currency_based.id,
            reimbursement_organization_settings_allowed_category_id=cycle_based_category_association.id,
            amount=cycle_based_category_association.num_cycles * NUM_CREDITS_PER_CYCLE,
        )
        currency_based_reimbursed_reimbursement.cost_credit = None
        benefit_type_converter.procedure_service.get_procedure_by_id.return_value = None

        # When
        with pytest.raises(BenefitTypeConversionError, match="Procedure is not found"):
            benefit_type_converter.convert_reimbursement_to_cycle(
                reimbursement_request=currency_based_reimbursed_reimbursement,
                new_category=cycle_based_category_association,
                cycle_credit=cycle_credit,
            )

    @staticmethod
    def test_convert_reimbursement_to_cycle_invalid_category(
        benefit_type_converter,
        wallet_currency_based,
        currency_based_reimbursed_reimbursement,
        currency_based_category_association,
        cycle_based_category_association,
    ):
        """Test that if the new_category is not a cycle category, we raise an exception"""
        # Given
        cycle_credit = ReimbursementCycleCreditsFactory.create(
            reimbursement_wallet_id=wallet_currency_based.id,
            reimbursement_organization_settings_allowed_category_id=cycle_based_category_association.id,
            amount=cycle_based_category_association.num_cycles * NUM_CREDITS_PER_CYCLE,
        )
        # When - Then
        with pytest.raises(
            BenefitTypeConversionValidationError,
            match=f"new_category is not of 'CYCLE' type: category association id: {str(currency_based_category_association.id)}",
        ):
            benefit_type_converter.convert_reimbursement_to_cycle(
                reimbursement_request=currency_based_reimbursed_reimbursement,
                new_category=currency_based_category_association,
                cycle_credit=cycle_credit,
            )


class TestConvertCurrencyToCycle:
    @staticmethod
    def test_convert_currency_to_cycle_invalid_currency_category(
        benefit_type_converter,
        wallet_cycle_based,
        cycle_based_category_association,
        currency_based_category_association,
    ):
        """Test that if the currency_category is not a currency category, we raise an exception"""
        # When - Then
        with pytest.raises(
            ValueError, match="currency_category is not of 'CURRENCY' type"
        ):
            benefit_type_converter.convert_currency_to_cycle(
                wallet=wallet_cycle_based,
                currency_category=cycle_based_category_association,
                cycle_category=cycle_based_category_association,
            )

    @staticmethod
    def test_convert_currency_to_cycle_invalid_cycle_category(
        benefit_type_converter,
        wallet_cycle_based,
        cycle_based_category_association,
        currency_based_category_association,
    ):
        """Test that if the cycle_category is not a cycle category, we raise an exception"""
        # When - Then
        with pytest.raises(ValueError, match="cycle_category is not of 'CYCLE' type"):
            benefit_type_converter.convert_currency_to_cycle(
                wallet=wallet_cycle_based,
                currency_category=currency_based_category_association,
                cycle_category=currency_based_category_association,
            )

    @staticmethod
    def test_convert_currency_to_cycle_single_reimbursed_reimbursement(
        benefit_type_converter,
        wallet_currency_based,
        currency_based_reimbursed_reimbursement,
        cycle_based_category_association,
        currency_based_category_association,
    ):
        """
        Test that the following conditions are met when we run convert_currency_to_cycle()
            1. New currency based category is assigned to the reimbursement request
            2. The amount of the REIMBURSED reimbursement is returned as part of the the total spend
        """
        # Given
        assert (
            currency_based_reimbursed_reimbursement.reimbursement_request_category_id
            == currency_based_category_association.reimbursement_request_category_id
        )
        benefit_type_converter.procedure_service.get_procedure_by_id.return_value = (
            GlobalProcedureFactory.create(credits=2)
        )

        # When
        usd_spend: int = benefit_type_converter.convert_currency_to_cycle(
            wallet=wallet_currency_based,
            currency_category=currency_based_category_association,
            cycle_category=cycle_based_category_association,
        )

        # Then
        assert (
            currency_based_reimbursed_reimbursement.reimbursement_request_category_id
            == cycle_based_category_association.reimbursement_request_category_id
        )
        assert usd_spend == 1_000_00

    @staticmethod
    def test_convert_currency_to_cycle_single_pending_reimbursement(
        benefit_type_converter,
        wallet_currency_based,
        currency_based_pending_reimbursement,
        cycle_based_category_association,
        currency_based_category_association,
    ):
        """
        Test that the following conditions are met when we run convert_currency_to_cycle()
            1. New cycle based category is assigned to the reimbursement request
            2. 0 is returned since the reimbursement is PENDING
        """
        # Given
        assert (
            currency_based_pending_reimbursement.reimbursement_request_category_id
            == currency_based_category_association.reimbursement_request_category_id
        )
        benefit_type_converter.procedure_service.get_procedure_by_id.return_value = (
            GlobalProcedureFactory.create(credits=2)
        )

        # When
        usd_spend: int = benefit_type_converter.convert_currency_to_cycle(
            wallet=wallet_currency_based,
            currency_category=currency_based_category_association,
            cycle_category=cycle_based_category_association,
        )

        # Then
        assert (
            currency_based_pending_reimbursement.reimbursement_request_category_id
            == cycle_based_category_association.reimbursement_request_category_id
        )
        assert usd_spend == 0

    @staticmethod
    def test_convert_currency_to_cycle_no_reimbursements(
        benefit_type_converter,
        wallet_currency_based,
        cycle_based_category_association,
        currency_based_category_association,
    ):
        """
        Test that the following conditions are met when we run convert_currency_to_cycle()
            1. 0 is returned since there are no reimbursements
        """
        # When
        usd_spend: int = benefit_type_converter.convert_currency_to_cycle(
            wallet=wallet_currency_based,
            currency_category=currency_based_category_association,
            cycle_category=cycle_based_category_association,
        )

        # Then
        assert usd_spend == 0

    @staticmethod
    def test_convert_currency_to_cycle_no_cycle_credits_exist(
        benefit_type_converter,
        wallet_currency_based,
        cycle_based_category_association,
        currency_based_category_association,
        session,
    ):
        """
        Test that ReimbursementCycleCredits and ReimbursementCycleMemberCreditTransaction is created when no CycleCredit exists for wallet/category
        """
        # Given
        expected_credit_amount = (
            cycle_based_category_association.num_cycles * NUM_CREDITS_PER_CYCLE
        )

        # When
        _ = benefit_type_converter.convert_currency_to_cycle(
            wallet=wallet_currency_based,
            currency_category=currency_based_category_association,
            cycle_category=cycle_based_category_association,
        )

        # Then
        cycle_credit = (
            session.query(ReimbursementCycleCredits)
            .filter(
                ReimbursementCycleCredits.reimbursement_wallet_id
                == wallet_currency_based.id,
                ReimbursementCycleCredits.reimbursement_organization_settings_allowed_category_id
                == cycle_based_category_association.id,
            )
            .one()
        )

        init_trans = (
            session.query(ReimbursementCycleMemberCreditTransaction)
            .filter(
                ReimbursementCycleMemberCreditTransaction.reimbursement_cycle_credits_id
                == cycle_credit.id,
            )
            .one()
        )

        assert cycle_credit
        assert cycle_credit.amount == expected_credit_amount
        assert init_trans
        assert init_trans.amount == expected_credit_amount
        assert init_trans.reimbursement_request_id is None
        assert init_trans.reimbursement_wallet_global_procedures_id is None

    @staticmethod
    def test_convert_currency_to_cycle_cycle_credits_exist(
        benefit_type_converter,
        wallet_currency_based,
        cycle_based_category_association,
        currency_based_category_association,
        session,
    ):
        """
        Test that ReimbursementCycleCredits and ReimbursementCycleMemberCreditTransaction is created when no CycleCredit exists for wallet/category
        """
        # Given
        expected_credit_amount = (
            cycle_based_category_association.num_cycles * NUM_CREDITS_PER_CYCLE
        )

        # When
        _ = benefit_type_converter.convert_currency_to_cycle(
            wallet=wallet_currency_based,
            currency_category=currency_based_category_association,
            cycle_category=cycle_based_category_association,
        )

        # Then
        cycle_credit = (
            session.query(ReimbursementCycleCredits)
            .filter(
                ReimbursementCycleCredits.reimbursement_wallet_id
                == wallet_currency_based.id,
                ReimbursementCycleCredits.reimbursement_organization_settings_allowed_category_id
                == cycle_based_category_association.id,
            )
            .one()
        )

        init_trans = (
            session.query(ReimbursementCycleMemberCreditTransaction)
            .filter(
                ReimbursementCycleMemberCreditTransaction.reimbursement_cycle_credits_id
                == cycle_credit.id,
            )
            .one()
        )

        assert cycle_credit
        assert cycle_credit.amount == expected_credit_amount
        assert init_trans
        assert init_trans.amount == expected_credit_amount
        assert init_trans.reimbursement_request_id is None
        assert init_trans.reimbursement_wallet_global_procedures_id is None


class TestReimbursementAccountExists:
    @staticmethod
    def test_reimbursement_account_exists(
        benefit_type_converter, wallet_cycle_based, cycle_based_category
    ):
        # Given
        _ = ReimbursementAccountFactory.create(
            wallet=wallet_cycle_based, plan=cycle_based_category.reimbursement_plan
        )

        # When
        account_exists = benefit_type_converter.reimbursement_account_exists(
            wallet=wallet_cycle_based, category=cycle_based_category
        )

        # Then
        assert account_exists == True

    @staticmethod
    def test_reimbursement_account_does_not_exist(
        benefit_type_converter, wallet_cycle_based, cycle_based_category
    ):
        # When
        account_exists = benefit_type_converter.reimbursement_account_exists(
            wallet=wallet_cycle_based, category=cycle_based_category
        )

        # Then
        assert account_exists == False


class TestSyncAlegeusAccounts:
    @staticmethod
    def test_sync_alegeus_accounts_no_prior_accounts_exist(
        benefit_type_converter,
        wallet_currency_based,
        cycle_based_category_association,
        currency_based_category_association,
        successful_alegeus_response,
    ):
        """Test when no prior accounts exist for target_category. This should be the majority of cases."""
        # Given
        remaining_balance = cycle_based_category_association.usd_funding_amount
        benefit_type_converter.alegeus_api.terminate_employee_account.return_value = (
            successful_alegeus_response
        )

        # When
        with mock.patch(
            "wallet.services.reimbursement_wallet_benefit_type_converter.configure_account"
        ) as mock_configure_account:
            mock_configure_account.return_value = True, None

            result = benefit_type_converter.sync_alegeus_accounts(
                wallet=wallet_currency_based,
                source_category=currency_based_category_association,
                target_category=cycle_based_category_association,
                remaining_balance=remaining_balance,
            )

        # Then
        assert result == True

    @staticmethod
    def test_sync_alegeus_accounts_prior_accounts_exist(
        benefit_type_converter,
        wallet_currency_based,
        cycle_based_category_association,
        cycle_based_category,
        currency_based_category_association,
        successful_alegeus_response,
    ):
        """Test when prior accounts exist for target_category. This is the back-and-forth conversion case (rare)"""
        # Given
        remaining_balance = 10_000_00
        benefit_type_converter.alegeus_api.terminate_employee_account.return_value = (
            successful_alegeus_response
        )
        successful_alegeus_response.json.return_value = {"RemainingBalance": "1000.00"}
        benefit_type_converter.alegeus_api.get_account_details.return_value = (
            successful_alegeus_response
        )
        benefit_type_converter.alegeus_api.reactivate_employee_account.return_value = (
            successful_alegeus_response
        )
        benefit_type_converter.alegeus_api.post_add_prefunded_deposit.return_value = (
            successful_alegeus_response
        )

        _ = ReimbursementAccountFactory.create(
            wallet=wallet_currency_based, plan=cycle_based_category.reimbursement_plan
        )

        # When
        result = benefit_type_converter.sync_alegeus_accounts(
            wallet=wallet_currency_based,
            source_category=currency_based_category_association,
            target_category=cycle_based_category_association,
            remaining_balance=remaining_balance,
        )

        # Then
        assert result == True
        benefit_type_converter.alegeus_api.post_add_prefunded_deposit.assert_called_with(
            wallet=wallet_currency_based,
            plan=cycle_based_category.reimbursement_plan,
            deposit_amount=9_000_00,
        )

    @staticmethod
    def test_sync_alegeus_accounts_error_while_terminating_account(
        benefit_type_converter,
        wallet_currency_based,
        cycle_based_category_association,
        currency_based_category_association,
        failed_alegeus_response,
    ):
        """Test when there is an error terminating an existing account."""
        # Given
        remaining_balance = cycle_based_category_association.usd_funding_amount
        benefit_type_converter.alegeus_api.terminate_employee_account.return_value = (
            failed_alegeus_response
        )

        # When - Then
        with pytest.raises(
            BenefitTypeConversionValidationError,
            match="Failed to terminate existing Alegeus account",
        ):
            _ = benefit_type_converter.sync_alegeus_accounts(
                wallet=wallet_currency_based,
                source_category=currency_based_category_association,
                target_category=cycle_based_category_association,
                remaining_balance=remaining_balance,
            )

    @staticmethod
    def test_sync_alegeus_accounts_error_while_creating_account(
        benefit_type_converter,
        wallet_currency_based,
        cycle_based_category_association,
        currency_based_category_association,
        successful_alegeus_response,
    ):
        """Test when there is an error while creating a new alegeus account."""
        # Given
        remaining_balance = cycle_based_category_association.usd_funding_amount
        benefit_type_converter.alegeus_api.terminate_employee_account.return_value = (
            successful_alegeus_response
        )

        # When - Then
        with mock.patch(
            "wallet.services.reimbursement_wallet_benefit_type_converter.configure_account"
        ) as mock_configure_account, pytest.raises(
            BenefitTypeConversionValidationError,
            match="Failed to configure new Alegeus account",
        ):
            mock_configure_account.return_value = False, None

            _ = benefit_type_converter.sync_alegeus_accounts(
                wallet=wallet_currency_based,
                source_category=currency_based_category_association,
                target_category=cycle_based_category_association,
                remaining_balance=remaining_balance,
            )

    @staticmethod
    def test_sync_alegeus_accounts_prior_accounts_exist_failed_to_get_account_details(
        benefit_type_converter,
        wallet_currency_based,
        cycle_based_category_association,
        cycle_based_category,
        currency_based_category_association,
        successful_alegeus_response,
        failed_alegeus_response,
    ):
        """Test when there is an error while getting account balance from alegeus"""
        # Given
        remaining_balance = cycle_based_category_association.usd_funding_amount
        benefit_type_converter.alegeus_api.terminate_employee_account.return_value = (
            successful_alegeus_response
        )

        _ = ReimbursementAccountFactory.create(
            wallet=wallet_currency_based, plan=cycle_based_category.reimbursement_plan
        )

        # When - Then
        with mock.patch(
            "wallet.services.reimbursement_wallet_benefit_type_converter.get_employee_account"
        ) as mock_get_employee_account, pytest.raises(
            BenefitTypeConversionValidationError,
            match="Failed to fetch existing Alegeus account details",
        ):
            mock_get_employee_account.return_value = False, None

            _ = benefit_type_converter.sync_alegeus_accounts(
                wallet=wallet_currency_based,
                source_category=currency_based_category_association,
                target_category=cycle_based_category_association,
                remaining_balance=remaining_balance,
            )

    @staticmethod
    def test_sync_alegeus_accounts_prior_accounts_exist_failed_to_reactivate_existing_account(
        benefit_type_converter,
        wallet_currency_based,
        cycle_based_category_association,
        cycle_based_category,
        currency_based_category_association,
        successful_alegeus_response,
        failed_alegeus_response,
    ):
        """Test when there is an error while reactivating existing alegeus account."""
        # Given
        remaining_balance = cycle_based_category_association.usd_funding_amount
        benefit_type_converter.alegeus_api.terminate_employee_account.return_value = (
            successful_alegeus_response
        )
        successful_alegeus_response.json.return_value = {"RemainingBalance": "1000.00"}
        benefit_type_converter.alegeus_api.get_account_details.return_value = (
            successful_alegeus_response
        )
        benefit_type_converter.alegeus_api.reactivate_employee_account.return_value = (
            failed_alegeus_response
        )

        _ = ReimbursementAccountFactory.create(
            wallet=wallet_currency_based, plan=cycle_based_category.reimbursement_plan
        )

        # When - Then
        with pytest.raises(
            BenefitTypeConversionValidationError,
            match="Failed to reactivate existing Alegeus account",
        ):
            _ = benefit_type_converter.sync_alegeus_accounts(
                wallet=wallet_currency_based,
                source_category=currency_based_category_association,
                target_category=cycle_based_category_association,
                remaining_balance=remaining_balance,
            )

    @staticmethod
    def test_sync_alegeus_accounts_prior_accounts_exist_failed_adjust_existing_account_balance(
        benefit_type_converter,
        wallet_currency_based,
        cycle_based_category_association,
        cycle_based_category,
        currency_based_category_association,
        successful_alegeus_response,
        failed_alegeus_response,
    ):
        """Test when there is an error while updating existing Alegeus account balance."""
        # Given
        remaining_balance = cycle_based_category_association.usd_funding_amount
        benefit_type_converter.alegeus_api.terminate_employee_account.return_value = (
            successful_alegeus_response
        )
        successful_alegeus_response.json.return_value = {"RemainingBalance": "1000.00"}
        benefit_type_converter.alegeus_api.get_account_details.return_value = (
            successful_alegeus_response
        )
        benefit_type_converter.alegeus_api.reactivate_employee_account.return_value = (
            successful_alegeus_response
        )
        benefit_type_converter.alegeus_api.post_add_prefunded_deposit.return_value = (
            failed_alegeus_response
        )

        _ = ReimbursementAccountFactory.create(
            wallet=wallet_currency_based, plan=cycle_based_category.reimbursement_plan
        )

        # When - Then
        with pytest.raises(
            BenefitTypeConversionValidationError,
            match="Failed to adjust Alegeus account balance",
        ):
            _ = benefit_type_converter.sync_alegeus_accounts(
                wallet=wallet_currency_based,
                source_category=currency_based_category_association,
                target_category=cycle_based_category_association,
                remaining_balance=remaining_balance,
            )


class TestUpdateTreatmentProcedures:
    @staticmethod
    def test_batch_update_treatment_procedure_category(
        benefit_type_converter,
        wallet_currency_based,
        currency_based_scheduled_treatment_procedure,
        cycle_based_category_association,
    ):
        # Given
        tps = [currency_based_scheduled_treatment_procedure]

        # When
        updated_tps = benefit_type_converter.batch_update_treatment_procedure_category(
            wallet=wallet_currency_based,
            treatment_procedures=tps,
            new_category=cycle_based_category_association,
        )

        # THen
        assert len(updated_tps) == 1
        assert (
            currency_based_scheduled_treatment_procedure.reimbursement_request_category_id
            == cycle_based_category_association.reimbursement_request_category_id
        )

    @staticmethod
    def test_batch_update_treatment_procedure_cost_credit(
        benefit_type_converter,
        wallet_currency_based,
        currency_based_scheduled_treatment_procedure,
        cycle_based_category_association,
    ):
        # Given
        benefit_type_converter.procedure_service.get_procedure_by_id.return_value = (
            GlobalProcedureFactory.create(credits=2)
        )
        tps = [currency_based_scheduled_treatment_procedure]
        assert currency_based_scheduled_treatment_procedure.cost_credit is None

        # When
        updated_tps = (
            benefit_type_converter.batch_update_treatment_procedure_cost_credit(
                wallet=wallet_currency_based,
                treatment_procedures=tps,
                new_category=cycle_based_category_association,
            )
        )

        # THen
        assert len(updated_tps) == 1
        assert currency_based_scheduled_treatment_procedure.cost_credit == 2

    @staticmethod
    def test_batch_update_treatment_procedure_cost_credit_gp_not_found(
        benefit_type_converter,
        wallet_currency_based,
        currency_based_scheduled_treatment_procedure,
        cycle_based_category_association,
    ):
        # Given
        benefit_type_converter.procedure_service.get_procedure_by_id.return_value = None
        tps = [currency_based_scheduled_treatment_procedure]

        # When
        with pytest.raises(BenefitTypeConversionError, match="Procedure is not found"):
            benefit_type_converter.batch_update_treatment_procedure_cost_credit(
                wallet=wallet_currency_based,
                treatment_procedures=tps,
                new_category=cycle_based_category_association,
            )

    @staticmethod
    def test_batch_update_nullify_treatment_procedure_cost_credit(
        benefit_type_converter,
        wallet_currency_based,
        currency_based_scheduled_treatment_procedure,
        cycle_based_category_association,
    ):
        # Given
        currency_based_scheduled_treatment_procedure.cost_credit = 2
        tps = [currency_based_scheduled_treatment_procedure]

        # When
        updated_tps = (
            benefit_type_converter.batch_update_nullify_treatment_procedure_cost_credit(
                wallet=wallet_currency_based,
                treatment_procedures=tps,
            )
        )

        # THen
        assert len(updated_tps) == 1
        assert currency_based_scheduled_treatment_procedure.cost_credit is None
