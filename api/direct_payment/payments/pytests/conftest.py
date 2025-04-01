import datetime
import uuid

import factory
import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.billing import models as billing_models
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.pytests import factories as billing_factories
from direct_payment.billing.pytests.conftest import bill_repository  # noqa: F401
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests import factories as procedure_factories
from pytests import factories
from wallet.models.constants import WalletUserStatus, WalletUserType
from wallet.pytests import factories as wallet_factories


@pytest.fixture
def billing_service(session):
    return BillingService(session=session)


@pytest.fixture
def bill_user():
    user = factories.EnterpriseUserFactory.create()
    return user


@pytest.fixture
def bill_wallet(bill_user):
    wallet = wallet_factories.ReimbursementWalletFactory.create(
        payments_customer_id=str(uuid.uuid4())
    )
    factories.ReimbursementWalletUsersFactory.create(
        user_id=bill_user.id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.EMPLOYEE,
    )
    return wallet


@pytest.fixture
def procedure(bill_wallet):
    return procedure_factories.TreatmentProcedureFactory.create(
        reimbursement_wallet_id=bill_wallet.id,
    )


@pytest.fixture
def cancelled_procedure(bill_wallet):
    return procedure_factories.TreatmentProcedureFactory.create(
        reimbursement_wallet_id=bill_wallet.id,
        status=TreatmentProcedureStatus.CANCELLED,
    )


@pytest.fixture
def procedure_fixture():
    def fn(inp_wallet, proc_status):
        return procedure_factories.TreatmentProcedureFactory.create(
            reimbursement_wallet_id=inp_wallet.id, status=proc_status
        )

    return fn


@pytest.fixture
def add_association_for_procedure_and_wallet():
    def add_association(procedure, wallet, benefit_type):
        wallet_factories.ReimbursementOrgSettingCategoryAssociationFactory.create(
            reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
            reimbursement_request_category_id=procedure.reimbursement_request_category_id,
            benefit_type=benefit_type,
        )

    return add_association


@pytest.fixture
def cost_breakdown(procedure):
    return CostBreakdownFactory.create(
        treatment_procedure_uuid=procedure.uuid, wallet_id=10011
    )


@pytest.fixture
def cost_breakdown_for_cancelled_procedure(cancelled_procedure):
    return CostBreakdownFactory.create(
        treatment_procedure_uuid=cancelled_procedure.uuid, wallet_id=10011
    )


@pytest.fixture
def past_historic_cost_breakdown(procedure, cost_breakdown):
    # a cost breakdown created before our billed cost breakdown
    return CostBreakdownFactory.create(
        treatment_procedure_uuid=procedure.uuid,
        created_at=cost_breakdown.created_at - datetime.timedelta(days=2),
        wallet_id=22022,
    )


@pytest.fixture
def historic_bill(
    procedure,
    cost_breakdown,
    bill_wallet,
    billing_service,
):
    bill = billing_factories.BillFactory.build(
        procedure_id=procedure.id,
        cost_breakdown_id=cost_breakdown.id,
        payor_type=billing_models.PayorType.MEMBER,
        payor_id=bill_wallet.id,
    )
    bill = billing_service.bill_repo.create(instance=bill)
    return bill


@pytest.fixture
def bill_with_estimate(procedure, bill_wallet, billing_service):
    cost_breakdown = CostBreakdownFactory.create(
        treatment_procedure_uuid=procedure.uuid,
        wallet_id=bill_wallet.id,
        total_member_responsibility=100_00,
        total_employer_responsibility=90_00,
        beginning_wallet_balance=90_00,
        ending_wallet_balance=0,
    )
    bill = billing_factories.BillFactory.build(
        procedure_id=procedure.id,
        cost_breakdown_id=cost_breakdown.id,
        payor_type=billing_models.PayorType.MEMBER,
        payor_id=bill_wallet.id,
        is_ephemeral=True,
        processing_scheduled_at_or_after=None,
    )
    bill = billing_service.bill_repo.create(instance=bill)
    return bill


@pytest.fixture
def cost_breakdown_for_upcoming_bills(bill_wallet, procedure):
    return CostBreakdownFactory.create(
        treatment_procedure_uuid=procedure.uuid,
        wallet_id=bill_wallet.id,
        total_member_responsibility=2,
        total_employer_responsibility=1,
        oop_remaining=2,
    )


@pytest.fixture
def cost_breakdown_with_total_member_responsibility_and_total_employer_responsibility(
    procedure,
):
    def make_cost_breakdown(
        total_member_responsibility: int, total_employer_responsibility: int
    ):
        return CostBreakdownFactory.create(
            wallet_id=1212,
            treatment_procedure_uuid=procedure.uuid,
            total_member_responsibility=total_member_responsibility,
            total_employer_responsibility=total_employer_responsibility,
        )

    return make_cost_breakdown


@pytest.fixture
def upcoming_bills_fixture(
    bill_repository,  # noqa: F811
    bill_wallet,
    procedure_fixture,
    cost_breakdown_for_upcoming_bills,
):
    def fn(inp_wallet, proc_status, is_ephemeral):
        bills = billing_factories.BillFactory.build_batch(
            size=3,
            status=factory.Iterator(billing_models.UPCOMING_STATUS),
            procedure_id=procedure_fixture(inp_wallet, proc_status).id,
            cost_breakdown_id=cost_breakdown_for_upcoming_bills.id,
            payor_type=billing_models.PayorType.MEMBER,
            payor_id=bill_wallet.id,
            paid_at=factory.Iterator([None, None, datetime.datetime.utcnow()]),
            payment_method_label=factory.Iterator(
                ["wrong one", "this one should show", None]
            ),
            created_at=factory.Iterator(
                [
                    datetime.datetime(3000, 1, 1),
                    datetime.datetime(3000, 1, 20),
                    datetime.datetime(3000, 1, 2),
                ]
            ),
            is_ephemeral=factory.Iterator(is_ephemeral),
            processing_scheduled_at_or_after=factory.Iterator(
                [
                    datetime.datetime.strptime("2024-01-10", "%Y-%m-%d"),
                    datetime.datetime.strptime("2024-01-01", "%Y-%m-%d"),
                    datetime.datetime.strptime("2024-01-20", "%Y-%m-%d"),
                ]
            ),
        )
        return [bill_repository.create(instance=bill) for bill in bills]

    return fn


@pytest.fixture
def cancelled_bill(
    bill_wallet,
    cancelled_procedure,
    bill_repository,  # noqa: F811
    cost_breakdown_for_cancelled_procedure,
):
    bill = billing_factories.BillFactory.build(
        amount=1000,
        procedure_id=cancelled_procedure.id,
        payor_id=bill_wallet.id,
        status=billing_models.BillStatus.CANCELLED,
        cost_breakdown_id=cost_breakdown_for_cancelled_procedure.id,
        last_calculated_fee=100,
        payor_type=billing_models.PayorType.MEMBER,
        created_at=datetime.datetime(2024, 3, 1, 10, 30, 0),
        processing_scheduled_at_or_after=datetime.datetime(2024, 3, 4, 10, 30, 0),
        cancelled_at=datetime.datetime(2024, 3, 5, 10, 30, 0),
        processing_at=datetime.datetime(2024, 3, 3, 10, 30, 0),
    )
    return bill_repository.create(instance=bill)


@pytest.fixture
def bill_with_payment_status_and_cost_responsibility_type(
    bill_wallet,
    procedure,
    bill_repository,  # noqa: F811
    cost_breakdown_with_total_member_responsibility_and_total_employer_responsibility,
):
    def make_bill(
        total_member_responsibility: int,
        total_employer_responsibility: int,
        payment_status: billing_models.BillStatus,
    ):
        cost_breakdown = cost_breakdown_with_total_member_responsibility_and_total_employer_responsibility(
            total_member_responsibility=total_member_responsibility,
            total_employer_responsibility=total_employer_responsibility,
        )
        bill = billing_factories.BillFactory.build(
            amount=1000,
            procedure_id=procedure.id,
            payor_id=bill_wallet.id,
            status=payment_status,
            cost_breakdown_id=cost_breakdown.id,
            last_calculated_fee=100,
            payor_type=billing_models.PayorType.MEMBER,
            created_at=datetime.datetime(2024, 3, 1, 10, 30, 0),
            processing_scheduled_at_or_after=datetime.datetime(2024, 3, 4, 10, 30, 0),
            processing_at=datetime.datetime(2024, 3, 3, 10, 30, 0),
        )
        return bill_repository.create(instance=bill)

    return make_bill
