import random
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest import mock

import factory
import pytest

from direct_payment.billing import models
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.models import BillStatus, PayorType
from direct_payment.billing.pytests import factories as billing_factories
from direct_payment.billing.pytests.factories import BillFactory
from direct_payment.billing.repository.bill import BillRepository
from direct_payment.billing.repository.bill_processing_record import (
    BillProcessingRecordRepository,
)
from direct_payment.clinic.pytests.factories import FertilityClinicFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests import factories as procedure_factories
from models.verticals_and_specialties import CX_VERTICAL_NAME
from pytests import factories
from wallet.models.constants import WalletState
from wallet.pytests import factories as wallet_factories
from wallet.pytests.factories import (
    ReimbursementOrganizationSettingsFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementWalletBenefitFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
    ResourceFactory,
)


@pytest.fixture
def bill_repository(session):
    return BillRepository(session=session, is_in_uow=True)


@pytest.fixture
def bill_processing_record_repository(session):
    return BillProcessingRecordRepository(session=session, is_in_uow=True)


@pytest.fixture
def billing_service(session):
    return BillingService(session=session, is_in_uow=True)


@pytest.fixture
def member_payor_id():
    return 100


@pytest.fixture
def bill_user():
    user = factories.EnterpriseUserFactory.create()
    return user


@pytest.fixture
def ops_user():
    ca_vertical = factories.VerticalFactory.create(name=CX_VERTICAL_NAME)
    user = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[ca_vertical],
    )
    return user


@pytest.fixture
def bill_wallet(bill_user):
    wallet = wallet_factories.ReimbursementWalletFactory.create(
        payments_customer_id=str(uuid.uuid4())
    )
    factories.ReimbursementWalletUsersFactory.create(
        user_id=bill_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    return wallet


@pytest.fixture
def bill_procedure(bill_wallet, bill_user):
    reimbursement_category = (
        wallet_factories.ReimbursementRequestCategoryFactory.create(label="fertility")
    )
    # since the bill_wallet fixture was used, you do not need to create the wallet again
    return procedure_factories.TreatmentProcedureFactory.create(
        member_id=bill_user.id,
        reimbursement_wallet_id=bill_wallet.id,
        reimbursement_request_category=reimbursement_category,
        status=TreatmentProcedureStatus.COMPLETED,
    )


@pytest.fixture
def failed_bill(bill_wallet, bill_procedure, bill_repository):
    # NOTE: bill is a dataclass, so the SQLAlchemy Factory Create does not work
    bill = billing_factories.BillFactory.build(
        procedure_id=bill_procedure.id,
        payor_type=models.PayorType.MEMBER,
        payor_id=bill_wallet.id,
        status=models.BillStatus.FAILED,
    )
    return bill_repository.create(instance=bill)


@pytest.fixture
def new_bill(bill_wallet, bill_procedure, bill_repository):
    # NOTE: bill is a dataclass, so the SQLAlchemy Factory Create does not work
    bill = billing_factories.BillFactory.build(
        procedure_id=bill_procedure.id,
        payor_type=models.PayorType.MEMBER,
        payor_id=bill_wallet.id,
        status=models.BillStatus.NEW,
    )
    return bill_repository.create(instance=bill)


@pytest.fixture
def employer_bill(bill_procedure, bill_repository):
    bill = billing_factories.BillFactory.build(
        procedure_id=bill_procedure.id,
        payor_type=models.PayorType.EMPLOYER,
        payor_id=123,
        status=models.BillStatus.NEW,
    )
    return bill_repository.create(instance=bill)


@pytest.fixture
def multiple_pre_created_bills(bill_repository):
    dt_fmt = "%d/%m/%Y %H:%M"
    created_bills = [
        BillFactory.build(
            payor_id=1,
            amount=200,
            payor_type=models.PayorType.MEMBER,
            status=models.BillStatus.PAID,
            paid_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
            created_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
            processing_scheduled_at_or_after=datetime.now(timezone.utc)
            + timedelta(minutes=-60),
        ),
        BillFactory.build(
            payor_id=1,
            amount=300,
            payor_type=models.PayorType.MEMBER,
            status=models.BillStatus.NEW,
            created_at=datetime.strptime("13/11/2018 15:30", dt_fmt),
            processing_scheduled_at_or_after=datetime.now(timezone.utc)
            + timedelta(minutes=-60),
        ),
        BillFactory.build(
            payor_id=2,
            amount=-200,
            payor_type=models.PayorType.EMPLOYER,
            status=models.BillStatus.NEW,
            created_at=datetime.strptime("14/11/2018 15:30", dt_fmt),
            processing_scheduled_at_or_after=datetime.now(timezone.utc)
            + timedelta(minutes=-60),
        ),
        BillFactory.build(
            payor_id=2,
            amount=200,
            payor_type=models.PayorType.EMPLOYER,
            status=models.BillStatus.REFUNDED,
            created_at=datetime.strptime("15/11/2018 15:30", dt_fmt),
            processing_scheduled_at_or_after=datetime.now(timezone.utc)
            + timedelta(minutes=-60),
        ),
        BillFactory.build(
            payor_id=3,
            amount=500,
            payor_type=models.PayorType.MEMBER,
            status=models.BillStatus.NEW,
            created_at=datetime.strptime("14/11/2018 15:30", dt_fmt),
            processing_scheduled_at_or_after=datetime.now(timezone.utc)
            + timedelta(minutes=-60),
        ),
        BillFactory.build(
            payor_id=3,
            amount=500,
            payor_type=models.PayorType.MEMBER,
            status=models.BillStatus.PROCESSING,
            created_at=datetime.strptime("15/11/2018 15:30", dt_fmt),
            processing_scheduled_at_or_after=datetime.now(timezone.utc)
            + timedelta(minutes=-600),
        ),
    ]
    to_return = [bill_repository.create(instance=bill) for bill in created_bills]
    return to_return


@pytest.fixture
def member_bills_for_procedures_specific_times(bill_repository):
    dt_fmt = "%d/%m/%Y %H:%M"
    created_bills = [
        billing_factories.BillFactory.build(
            id=2,
            uuid=uuid.UUID("29d597db-d657-4ba8-953e-c5999abf2cb5"),
            procedure_id=0,
            payor_type=models.PayorType.MEMBER,
            status=models.BillStatus.PAID,
            paid_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
        ),
        billing_factories.BillFactory.build(
            id=4,
            uuid=uuid.UUID("6def363f-fccc-40c5-995f-5c8f16108500"),
            procedure_id=1,
            payor_type=models.PayorType.MEMBER,
            status=models.BillStatus.REFUNDED,
            refunded_at=datetime.strptime("13/11/2018 15:30", dt_fmt),
        ),
        billing_factories.BillFactory.build(
            id=6,
            uuid=uuid.UUID("6a11f6b3-2036-446e-a078-1d4acd5f9ec7"),
            procedure_id=1,
            payor_type=models.PayorType.MEMBER,
            status=models.BillStatus.NEW,
            created_at=datetime.strptime("15/11/2018 12:30", dt_fmt),
        ),
        billing_factories.BillFactory.build(
            id=8,
            uuid=uuid.UUID("b72711d4-f53d-45b3-b8ec-0097fdae4e37"),
            procedure_id=1,
            payor_type=models.PayorType.MEMBER,
            status=models.BillStatus.PAID,
            paid_at=datetime.strptime("15/11/2018 15:30", dt_fmt),
        ),
        billing_factories.BillFactory.build(
            id=10,
            uuid=uuid.UUID("9b2e178d-aaf7-47db-8ae7-d56c8efe8da2"),
            procedure_id=2,
            payor_type=models.PayorType.MEMBER,
            status=models.BillStatus.REFUNDED,
            refunded_at=datetime.strptime("19/11/2018 15:30", dt_fmt),
        ),
        billing_factories.BillFactory.build(
            id=3,
            uuid=factory.Faker("uuid4"),
            procedure_id=0,
            payor_type=models.PayorType.MEMBER,
            status=models.BillStatus.PAID,
            paid_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
        ),
        billing_factories.BillFactory.build(
            id=5,
            uuid=factory.Faker("uuid4"),
            procedure_id=1,
            payor_type=models.PayorType.MEMBER,
            status=models.BillStatus.REFUNDED,
            refunded_at=datetime.strptime("13/11/2018 15:30", dt_fmt),
        ),
        billing_factories.BillFactory.build(
            id=7,
            uuid=factory.Faker("uuid4"),
            procedure_id=1,
            payor_type=models.PayorType.MEMBER,
            status=models.BillStatus.NEW,
            created_at=datetime.strptime("15/11/2018 12:30", dt_fmt),
        ),
        billing_factories.BillFactory.build(
            id=9,
            uuid=factory.Faker("uuid4"),
            procedure_id=1,
            payor_type=models.PayorType.MEMBER,
            status=models.BillStatus.PAID,
            paid_at=datetime.strptime("15/11/2018 15:30", dt_fmt),
        ),
        billing_factories.BillFactory.build(
            id=11,
            uuid=factory.Faker("uuid4"),
            procedure_id=2,
            payor_type=models.PayorType.MEMBER,
            status=models.BillStatus.REFUNDED,
            refunded_at=datetime.strptime("19/11/2018 15:30", dt_fmt),
        ),
    ]
    to_return = [bill_repository.create(instance=bill) for bill in created_bills]
    return to_return


@pytest.fixture
def member_paid_with_bpr_for_bills(
    member_bills_for_procedures_specific_times, bill_processing_record_repository
):
    to_return = []
    for bill in member_bills_for_procedures_specific_times:
        created_at = bill.created_at + timedelta(seconds=10)
        record = billing_factories.BillProcessingRecordFactory.build(
            bill_id=bill.id,
            processing_record_type=f"test_{bill.id}",
            bill_status=bill.status.value,
            created_at=created_at,
            transaction_id=uuid.uuid4() if bill.id % 2 == 0 else None,
        )
        to_return.append(bill_processing_record_repository.create(instance=record))
    return to_return


@pytest.fixture(scope="function")
def reimbursement_wallet_benefit():
    return ReimbursementWalletBenefitFactory.create()


@pytest.fixture(scope="function")
def reimbursement_benefit_resource():
    return ResourceFactory.create()


@pytest.fixture(scope="function")
def reimbursement_wallet(
    enterprise_user, reimbursement_wallet_benefit, reimbursement_benefit_resource
):
    org_settings = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id,
        allowed_reimbursement_categories__cycle_based=True,
        direct_payment_enabled=True,
    )
    org_settings.benefit_overview_resource_id = reimbursement_benefit_resource.id
    org_settings.benefit_overview_resource = reimbursement_benefit_resource
    wallet = ReimbursementWalletFactory.create(payments_customer_id=str(uuid.uuid4()))
    wallet.reimbursement_organization_settings = org_settings
    wallet.user_id = enterprise_user.id
    wallet.reimbursement_wallet_benefit = reimbursement_wallet_benefit
    wallet.reimbursement_wallet_benefit = reimbursement_wallet_benefit
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    return wallet


@pytest.fixture(scope="function")
def reimbursement_plan(reimbursement_wallet):
    today = date.today()

    new_category = ReimbursementRequestCategoryFactory.create(
        label="One Request Category"
    )

    plan = ReimbursementPlanFactory.create(
        category=new_category,
        start_date=today - timedelta(days=4),
        end_date=today - timedelta(days=2),
    )

    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category=new_category,
        reimbursement_organization_settings=reimbursement_wallet.reimbursement_organization_settings,
        reimbursement_request_category_maximum=0,
    )

    return plan


@pytest.fixture()
def random_reimbursement_wallet_with_benefit(enterprise_user):
    def fn():
        with mock.patch(
            "wallet.models.reimbursement_wallet.ReimbursementWallet.all_active_users",
            new_callable=mock.PropertyMock,
        ):
            to_return = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
            to_return.all_active_users.return_value = [to_return.user_id]

            ReimbursementWalletBenefitFactory.create(
                reimbursement_wallet_id=to_return.id,
                incremental_id=random.randrange(10000, 90101),
                maven_benefit_id=str(
                    to_return.id,
                ),
            )
            ReimbursementWalletUsersFactory.create(
                user_id=enterprise_user.id,
                reimbursement_wallet_id=to_return.id,
            )

            return to_return

    return fn


@pytest.fixture
def new_member_bills_for_processing(billing_service):
    created_bills = billing_factories.BillFactory.build_batch(
        size=8,
        payor_type=factory.Iterator(
            [models.PayorType.MEMBER] * 7 + [models.PayorType.EMPLOYER]
        ),
        status=factory.Iterator(
            [
                models.BillStatus.NEW,
                models.BillStatus.NEW,
                models.BillStatus.NEW,
                models.BillStatus.NEW,
                models.BillStatus.NEW,
                models.BillStatus.FAILED,
                models.BillStatus.PAID,
                models.BillStatus.NEW,
            ]
        ),
        created_at=factory.Iterator(
            [
                datetime(2024, 3, 1, 9, 15, 30),
                datetime(2024, 3, 2, 9, 15, 30),
                datetime(2024, 3, 2, 9, 30, 0),
                datetime(2024, 3, 3, 9, 30, 0),
                datetime(2024, 3, 4, 9, 30, 0),
                datetime(2024, 3, 4, 9, 30, 0),
                datetime(2024, 3, 2, 9, 30, 0),
                datetime(2024, 3, 2, 9, 30, 0),
            ]
        ),
        processing_scheduled_at_or_after=factory.Iterator(
            [
                None,
                None,
                None,
                datetime(2024, 3, 10, 9, 30, 00),
                datetime(2024, 3, 10, 9, 35, 00),
                datetime(2024, 3, 10, 9, 35, 00),
                None,
                None,
            ]
        ),
    )
    to_return = [
        billing_service.bill_repo.create(instance=bill) for bill in created_bills
    ]
    return to_return


@pytest.fixture
def several_bills_two_estimates(bill_repository, member_payor_id):
    created_bills = [
        billing_factories.BillFactory.build(
            procedure_id=4,
            payor_type=PayorType.MEMBER,
            payor_id=member_payor_id,
            status=BillStatus.NEW,
            processing_scheduled_at_or_after=None,
            is_ephemeral=True,
            created_at=datetime.now(timezone.utc) - timedelta(days=7),
        ),
        billing_factories.BillFactory.build(
            procedure_id=5,
            payor_type=PayorType.MEMBER,
            payor_id=member_payor_id,
            status=BillStatus.NEW,
            is_ephemeral=True,
            processing_scheduled_at_or_after=None,
            created_at=datetime.now(timezone.utc),
        ),
        billing_factories.BillFactory.build(
            procedure_id=6,
            payor_type=PayorType.EMPLOYER,
            payor_id=member_payor_id,
            status=BillStatus.NEW,
            processing_scheduled_at_or_after=None,
        ),
        billing_factories.BillFactory.build(
            procedure_id=7,
            payor_type=PayorType.MEMBER,
            payor_id=2,
            status=BillStatus.NEW,
            is_ephemeral=True,
            processing_scheduled_at_or_after=None,
        ),
        billing_factories.BillFactory.build(
            procedure_id=8,
            payor_type=PayorType.CLINIC,
            payor_id=member_payor_id,
            status=BillStatus.NEW,
            processing_scheduled_at_or_after=datetime.now(timezone.utc),
        ),
        billing_factories.BillFactory.build(
            procedure_id=9,
            payor_type=PayorType.MEMBER,
            payor_id=member_payor_id,
            status=BillStatus.PAID,
            processing_scheduled_at_or_after=None,
        ),
    ]
    res = []
    for bill in created_bills:
        res.append(bill_repository.create(instance=bill))
    return res


@pytest.fixture
def clinic():
    return FertilityClinicFactory.create()


@pytest.fixture
def employer():
    employer = ReimbursementOrganizationSettingsFactory.create(organization_id=1)
    employer.payments_customer_id = str(uuid.uuid4())
    return employer


@pytest.fixture
def member(bill_wallet, employer):
    bill_wallet.reimbursement_organization_settings_id = employer.id
    bill_wallet.reimbursement_organization_settings = employer
    return bill_wallet
