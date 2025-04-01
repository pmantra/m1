import datetime
import json

import pytest
from requests import Response

from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.models import BillStatus, PayorType
from direct_payment.billing.pytests.factories import BillFactory
from direct_payment.billing.repository import (
    BillProcessingRecordRepository,
    BillRepository,
)
from direct_payment.clinic.pytests.factories import FeeScheduleGlobalProceduresFactory
from direct_payment.invoicing.pytests import factories
from direct_payment.invoicing.repository.direct_payment_invoice import (
    DirectPaymentInvoiceRepository,
)
from direct_payment.invoicing.repository.direct_payment_invoice_bill_allocation import (
    DirectPaymentInvoiceBillAllocationRepository,
)
from direct_payment.invoicing.repository.organization_invoicing_settings import (
    OrganizationInvoicingSettingsRepository,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from pytests.common.global_procedures.factories import GlobalProcedureFactory
from pytests.factories import OrganizationFactory
from wallet.models.constants import ReimbursementRequestExpenseTypes, WalletState
from wallet.pytests.factories import (
    ReimbursementOrganizationSettingsFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementWalletFactory,
)


@pytest.fixture
def organization_invoicing_settings_repository(session):
    return OrganizationInvoicingSettingsRepository(session=session, is_in_uow=True)


@pytest.fixture
def new_organization_invoicing_settings(organization_invoicing_settings_repository):
    org = OrganizationFactory.create()
    ois = factories.OrganizationInvoicingSettingsFactory.build(organization_id=org.id)
    to_return = organization_invoicing_settings_repository.create(instance=ois)
    return to_return


@pytest.fixture
def new_organization_invoicing_settings_fixed_buffer(
    organization_invoicing_settings_repository,
):
    org = OrganizationFactory.create()
    ois = factories.OrganizationInvoicingSettingsFactory.build(
        organization_id=org.id, bill_processing_delay_days=2
    )
    to_return = organization_invoicing_settings_repository.create(instance=ois)
    return to_return


@pytest.fixture
def new_organization_invoicing_setting_invalid_cadence(
    organization_invoicing_settings_repository,
):
    org = OrganizationFactory.create()
    ois = factories.OrganizationInvoicingSettingsFactory.build(
        organization_id=org.id, bill_processing_delay_days=2, invoice_cadence="lol"
    )
    to_return = organization_invoicing_settings_repository.create(instance=ois)
    return to_return


@pytest.fixture
def direct_payment_invoice_repository(session):
    return DirectPaymentInvoiceRepository(session=session, is_in_uow=True)


@pytest.fixture
def new_direct_payment_invoice(direct_payment_invoice_repository):
    ros = ReimbursementOrganizationSettingsFactory.create(organization_id=9000)
    ois = factories.DirectPaymentInvoiceFactory.build(
        reimbursement_organization_settings_id=ros.id
    )
    to_return = direct_payment_invoice_repository.create(instance=ois)
    return to_return


@pytest.fixture
def new_direct_payment_invoice_for_ros(direct_payment_invoice_repository):
    def fn(ros, bill_creation_start_end_at, bill_creation_cutoff_end_at):
        # ros = ReimbursementOrganizationSettingsFactory.create(organization_id=9000)
        ois = factories.DirectPaymentInvoiceFactory.build(
            reimbursement_organization_settings_id=ros.id,
            bill_creation_cutoff_start_at=bill_creation_start_end_at,
            bill_creation_cutoff_end_at=bill_creation_cutoff_end_at,
        )
        to_return = direct_payment_invoice_repository.create(instance=ois)
        return to_return

    return fn


@pytest.fixture
def direct_payment_invoice_bill_allocation_repository(session):
    return DirectPaymentInvoiceBillAllocationRepository(session=session, is_in_uow=True)


@pytest.fixture
def new_direct_payment_invoice_bill_allocation(
    direct_payment_invoice_bill_allocation_repository, new_direct_payment_invoice
):
    to_return = direct_payment_invoice_bill_allocation_repository.create(
        instance=(
            factories.DirectPaymentInvoiceBillAllocationFactory.build(
                direct_payment_invoice_id=new_direct_payment_invoice.id
            )
        )
    )
    return to_return


@pytest.fixture
def billing_service(session):
    return BillingService(session=session, is_in_uow=True)


@pytest.fixture
def bill_repository(session):
    return BillRepository(session=session, is_in_uow=True)


@pytest.fixture
def bill_processing_record_repository(session):
    return BillProcessingRecordRepository(session=session, is_in_uow=True)


@pytest.fixture
def global_procedure():
    return GlobalProcedureFactory.create(name="IVF", credits=5)


@pytest.fixture
def wallet(session, enterprise_user):
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user, state=WalletState.QUALIFIED
    )
    wallet.reimbursement_organization_settings.direct_payment_enabled = True
    wallet.member.member_profile.country_code = "US"
    category_association = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[0]
    )
    category_association.is_direct_payment_eligible = True
    request_category = category_association.reimbursement_request_category
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=request_category,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )
    year = datetime.datetime.utcnow().year
    ReimbursementPlanFactory.create(
        category=request_category,
        start_date=datetime.datetime(year, 1, 1).date(),
        end_date=datetime.datetime(year, 12, 31).date(),
    )
    return wallet


@pytest.fixture
def treatment_procedure(session, global_procedure, wallet):
    member_id = wallet.member.id
    global_procedure = GlobalProcedureFactory.create()
    fee_schedule_global_procedures = FeeScheduleGlobalProceduresFactory.create(
        cost=34, global_procedure_id=global_procedure["id"]
    )
    fee_schedule = fee_schedule_global_procedures.fee_schedule
    procedure_name = global_procedure["name"]
    category = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
    )

    return TreatmentProcedureFactory.create(
        member_id=member_id,
        reimbursement_wallet_id=wallet.id,
        reimbursement_request_category=category,
        fee_schedule=fee_schedule,
        global_procedure_id=global_procedure["id"],
        procedure_name=procedure_name,
        cost=fee_schedule_global_procedures.cost,
    )


@pytest.fixture
def invoice_bills(
    treatment_procedure,
    direct_payment_invoice_bill_allocation_repository,
    bill_repository,
    new_direct_payment_invoice,
):
    # not an EMPLOYER bill
    bill_one = BillFactory.build(
        payor_type=PayorType.MEMBER,
        processing_scheduled_at_or_after=datetime.datetime.utcnow()
        - datetime.timedelta(days=1),
    )

    # not a NEW bill
    bill_two = BillFactory.build(
        payor_type=PayorType.EMPLOYER,
        status=BillStatus.PROCESSING,
        processing_scheduled_at_or_after=datetime.datetime.utcnow()
        - datetime.timedelta(days=1),
    )

    # not a ready-to-process bill
    bill_three = BillFactory.build(
        payor_type=PayorType.EMPLOYER,
        status=BillStatus.NEW,
        processing_scheduled_at_or_after=datetime.datetime.utcnow()
        + datetime.timedelta(days=1),
    )

    # a bill with a small amount
    bill_four = BillFactory.build(
        payor_type=PayorType.EMPLOYER,
        status=BillStatus.NEW,
        processing_scheduled_at_or_after=datetime.datetime.utcnow()
        - datetime.timedelta(days=2),
        amount=0,
        procedure_id=treatment_procedure.id,
    )

    # not a bill associated with an invoice
    bill_five = BillFactory.build(
        payor_type=PayorType.EMPLOYER,
        status=BillStatus.NEW,
        processing_scheduled_at_or_after=datetime.datetime.utcnow()
        - datetime.timedelta(days=2),
    )

    bill_six = BillFactory.build(
        payor_type=PayorType.EMPLOYER,
        status=BillStatus.NEW,
        processing_scheduled_at_or_after=datetime.datetime.utcnow()
        - datetime.timedelta(days=1),
    )

    bill_repository.create(instance=bill_one)
    bill_repository.create(instance=bill_two)
    bill_repository.create(instance=bill_three)
    bill_repository.create(instance=bill_four)
    bill_repository.create(instance=bill_five)
    bill_repository.create(instance=bill_six)

    direct_payment_invoice_bill_allocation_repository.create(
        instance=(
            factories.DirectPaymentInvoiceBillAllocationFactory.build(
                direct_payment_invoice_id=new_direct_payment_invoice.id,
                bill_uuid=bill_one.uuid,
            )
        )
    )

    direct_payment_invoice_bill_allocation_repository.create(
        instance=(
            factories.DirectPaymentInvoiceBillAllocationFactory.build(
                direct_payment_invoice_id=new_direct_payment_invoice.id,
                bill_uuid=bill_two.uuid,
            )
        )
    )

    direct_payment_invoice_bill_allocation_repository.create(
        instance=(
            factories.DirectPaymentInvoiceBillAllocationFactory.build(
                direct_payment_invoice_id=new_direct_payment_invoice.id,
                bill_uuid=bill_three.uuid,
            )
        )
    )

    direct_payment_invoice_bill_allocation_repository.create(
        instance=(
            factories.DirectPaymentInvoiceBillAllocationFactory.build(
                direct_payment_invoice_id=new_direct_payment_invoice.id,
                bill_uuid=bill_four.uuid,
            )
        )
    )

    direct_payment_invoice_bill_allocation_repository.create(
        instance=(
            factories.DirectPaymentInvoiceBillAllocationFactory.build(
                direct_payment_invoice_id=new_direct_payment_invoice.id,
                bill_uuid=bill_six.uuid,
            )
        )
    )

    return [bill_one, bill_two, bill_three, bill_four, bill_five, bill_six]


@pytest.fixture
def create_mock_response_fixture():
    def create_mock_response(transaction_data, uuid_param_str, metadata):
        content = json.dumps(
            {
                "transaction_id": uuid_param_str,
                "transaction_data": transaction_data,
                "status": "completed",
                "metadata": metadata or {},
            }
        )
        mock_response = Response()
        mock_response._content = content.encode("utf-8")
        mock_response.status_code = 200
        return mock_response

    return create_mock_response
