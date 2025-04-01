import pytest

from cost_breakdown.models.cost_breakdown import CostBreakdown
from data_admin.makers.cost_breakdown import CostBreakdownMaker
from data_admin.views import apply_specs
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from pytests.factories import EnterpriseUserFactory
from wallet.models.constants import WalletState
from wallet.pytests.factories import (
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
)


def test_cost_breakdown_fixture(data_admin_app, load_fixture):
    # given
    EnterpriseUserFactory.create(email="test+staff@mavenclinic.com")
    fixture = load_fixture("wallet/cost_breakdown.json")

    # when
    with data_admin_app.test_request_context():
        created, errors = apply_specs(fixture)

    # then
    assert isinstance(
        created[0], CostBreakdown
    ), f"Errors in applying the fixture: {', '.join(errors)}"


def test_cost_breakdown__successful():
    # Given
    enterprise_user = EnterpriseUserFactory.create(email="test+staff@mavenclinic.com")
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user, state=WalletState.QUALIFIED
    )
    tp = TreatmentProcedureFactory.create(reimbursement_wallet_id=wallet.id)
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    ReimbursementRequestFactory.create(
        reimbursement_wallet_id=wallet.id, reimbursement_request_category_id=category.id
    )
    cost_breakdown_spec = {
        "user_email": enterprise_user.email,
        "treatment_procedure_id": tp.id,
    }
    # When
    cost_breakdown = CostBreakdownMaker().create_object_and_flush(
        spec=cost_breakdown_spec
    )
    # Then
    assert cost_breakdown


def test_cost_breakdown__missing_required_param():
    # Given
    cost_breakdown_spec = {}
    # When
    with pytest.raises(ValueError) as error_msg:
        CostBreakdownMaker().create_object_and_flush(spec=cost_breakdown_spec)
    # Then
    assert str(error_msg.value) == "Missing param(s): ['user_email']"
