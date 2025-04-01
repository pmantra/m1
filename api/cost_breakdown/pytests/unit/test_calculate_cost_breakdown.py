from datetime import date
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.exc import OperationalError

from cost_breakdown.errors import (
    CostBreakdownDatabaseException,
    PayerDisabledCostBreakdownException,
)
from cost_breakdown.tasks.calculate_cost_breakdown import calculate_cost_breakdown
from direct_payment.clinic.pytests.factories import FertilityClinicFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from wallet.models.constants import AlegeusClaimStatus, ReimbursementRequestState
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    ReimbursementClaimFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
)
from wallet.utils.alegeus.claims.sync import get_wallet_with_pending_claims


@pytest.fixture(scope="function")
def wallet_with_pending_claims(wallet):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")

    pending_request = ReimbursementRequestFactory.create(
        wallet=wallet,
        category=category,
        state=ReimbursementRequestState.PENDING,
    )
    ReimbursementClaimFactory.create(
        alegeus_claim_id="123abc",
        status=AlegeusClaimStatus.NEEDS_RECEIPT.value,
        reimbursement_request=pending_request,
        alegeus_claim_key=1,
        amount=100.00,
    )

    return wallet


def test_calculate_cost_breakdown_async_no_sync_claims(wallet):
    request_category = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
    )
    wallet_user = ReimbursementWalletUsers.query.filter(
        ReimbursementWalletUsers.reimbursement_wallet_id == wallet.id
    ).one()
    treatment_procedure = TreatmentProcedureFactory.create(
        member_id=wallet_user.user_id,
        fertility_clinic=FertilityClinicFactory(),
        reimbursement_request_category=request_category,
        start_date=date.today(),
        status=TreatmentProcedureStatus.COMPLETED,
    )

    with patch(
        "cost_breakdown.tasks.calculate_cost_breakdown.sync_pending_claims"
    ) as sync_pending_claims_mock, patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_cost_breakdown_for_treatment_procedure",
        return_value=Mock(id=1),
    ):
        calculate_cost_breakdown(
            wallet_id=wallet.id, treatment_procedure_id=treatment_procedure.id
        )
        sync_pending_claims_mock.assert_not_called()


def test_calculate_cost_breakdown_async_sync_claims(wallet_with_pending_claims):
    request_category = wallet_with_pending_claims.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    wallet_user = ReimbursementWalletUsers.query.filter(
        ReimbursementWalletUsers.reimbursement_wallet_id
        == wallet_with_pending_claims.id
    ).one()
    treatment_procedure = TreatmentProcedureFactory.create(
        member_id=wallet_user.user_id,
        fertility_clinic=FertilityClinicFactory(),
        reimbursement_request_category=request_category,
        start_date=date.today(),
        status=TreatmentProcedureStatus.COMPLETED,
    )

    # with patch('wallet.utils.alegeus.claims.sync.sync_pending_claims') as sync_pending_claims_mock:
    with patch(
        "cost_breakdown.tasks.calculate_cost_breakdown.sync_pending_claims"
    ) as sync_pending_claims_mock, patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_cost_breakdown_for_treatment_procedure",
        return_value=Mock(id=1),
    ):
        calculate_cost_breakdown(
            wallet_id=wallet_with_pending_claims.id,
            treatment_procedure_id=treatment_procedure.id,
        )
        wallet_with_claims = get_wallet_with_pending_claims(
            wallet=wallet_with_pending_claims
        )
        sync_pending_claims_mock.assert_called_once()
        sync_pending_claims_mock.assert_called_once_with([wallet_with_claims])


def test_calculate_cost_breakdown_database_exception(wallet):
    request_category = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
    )
    wallet_user = ReimbursementWalletUsers.query.filter(
        ReimbursementWalletUsers.reimbursement_wallet_id == wallet.id
    ).one()
    treatment_procedure = TreatmentProcedureFactory.create(
        member_id=wallet_user.user_id,
        fertility_clinic=FertilityClinicFactory(),
        reimbursement_request_category=request_category,
        start_date=date.today(),
        status=TreatmentProcedureStatus.COMPLETED,
    )

    with patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_cost_breakdown_for_treatment_procedure",
        return_value=Mock(id=1),
    ) as get_cost_breakdown_for_treatment_procedure, pytest.raises(
        CostBreakdownDatabaseException
    ):
        get_cost_breakdown_for_treatment_procedure.side_effect = OperationalError(
            statement="SELECT * FROM table", params={}, orig=Exception()
        )
        calculate_cost_breakdown(
            wallet_id=wallet.id, treatment_procedure_id=treatment_procedure.id
        )


def test_calculate_cost_breakdown_payer_disabled(wallet):
    request_category = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
    )
    wallet_user = ReimbursementWalletUsers.query.filter(
        ReimbursementWalletUsers.reimbursement_wallet_id == wallet.id
    ).one()
    treatment_procedure = TreatmentProcedureFactory.create(
        member_id=wallet_user.user_id,
        fertility_clinic=FertilityClinicFactory(),
        reimbursement_request_category=request_category,
        start_date=date.today(),
        status=TreatmentProcedureStatus.COMPLETED,
    )

    with patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_cost_breakdown_for_treatment_procedure"
    ) as get_cost_breakdown_mock:
        get_cost_breakdown_mock.side_effect = PayerDisabledCostBreakdownException(
            "Cost breakdown disabled for payer TEST_PAYER."
        )
        calculate_cost_breakdown(
            wallet_id=wallet.id,
            treatment_procedure_id=treatment_procedure.id,
        )
    assert treatment_procedure.cost_breakdown_id is None
