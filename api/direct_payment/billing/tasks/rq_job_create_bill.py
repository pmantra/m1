from __future__ import annotations

from decimal import Decimal
from traceback import format_exc
from typing import List, Tuple

from common import stats
from common.payments_gateway import get_client
from cost_breakdown.constants import IS_INTEGRATIONS_K8S_CLUSTER
from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.billing import models
from direct_payment.billing.billing_service import (
    BillingService,
    from_employer_bill_create_clinic_bill_and_process,
)
from direct_payment.billing.constants import INTERNAL_TRUST_PAYMENT_GATEWAY_URL
from direct_payment.billing.lib.legacy_mono import (
    get_benefit_id_from_wallet_id,
    get_clinic_locations_as_dicts_from_treatment_procedure_id,
)
from direct_payment.billing.models import Bill, BillStatus, PayorType
from direct_payment.billing.tasks.lib.employer_bill_processing_functions import (
    can_employer_bill_be_auto_processed,
)
from direct_payment.notification.lib.tasks.rq_send_notification import (
    send_notification_event,
)
from direct_payment.pharmacy.tasks.libs.common import (
    UNAUTHENTICATED_PAYMENT_SERVICE_URL,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from storage.connection import db
from tasks.queues import job
from utils.log import logger
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)


@job("high_mem", ns_service="billing", team_ns="benefits_experience")
def create_member_and_employer_bill(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    treatment_procedure_id: int,
    cost_breakdown_id: int,
    wallet_id: int,
    treatment_procedure_status: TreatmentProcedureStatus,
):
    log.info(
        "Starting member and employer bill creation task.",
        treatment_procedure_id=str(treatment_procedure_id),
        cost_breakdown_id=str(cost_breakdown_id),
        wallet_id=str(wallet_id),
    )
    try:
        create_member_bill(
            treatment_procedure_id=treatment_procedure_id,
            cost_breakdown_id=cost_breakdown_id,
            wallet_id=wallet_id,
            treatment_procedure_status=treatment_procedure_status,
        )
        stats.increment(
            metric_name="direct_payment.billing.tasks.rq_job_create_bill.member_bill",
            pod_name=stats.PodNames.BENEFITS_EXP,
        )
    except Exception:
        log.error(
            "Member bill creation failed.",
            treatment_procedure_id=str(treatment_procedure_id),
            cost_breakdown_id=str(cost_breakdown_id),
            wallet_id=str(wallet_id),
            reason=format_exc(),
        )

    try:
        _create_employer_bill(
            treatment_procedure_id=treatment_procedure_id,
            cost_breakdown_id=cost_breakdown_id,
            wallet_id=wallet_id,
        )
        log.info(
            "Completed member and employer bill creation task.",
            treatment_procedure_id=str(treatment_procedure_id),
            cost_breakdown_id=str(cost_breakdown_id),
            wallet_id=str(wallet_id),
        )
    except Exception:
        log.error(
            "Employer bill creation failed.",
            treatment_procedure_id=treatment_procedure_id,
            cost_breakdown_id=cost_breakdown_id,
            wallet_id=str(wallet_id),
            reason=format_exc(),
        )


@job("high_mem", service_ns="billing", team_ns="benefits_experience")
def create_member_bill(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    treatment_procedure_id: int,
    cost_breakdown_id: int,
    wallet_id: int,
    treatment_procedure_status: TreatmentProcedureStatus,
):
    """
    Temporary RQ job to create bills as a background process. Will be replaced with pubsub.
    """
    log.info(
        "Starting member bill creation task.",
        treatment_procedure_id=str(treatment_procedure_id),
        cost_breakdown_id=str(cost_breakdown_id),
        wallet_id=str(wallet_id),
    )
    billing_service = BillingService(
        session=db.session,
        payment_gateway_base_url=(
            UNAUTHENTICATED_PAYMENT_SERVICE_URL
            if IS_INTEGRATIONS_K8S_CLUSTER
            else INTERNAL_TRUST_PAYMENT_GATEWAY_URL
        ),
    )
    _ = _create_bill(
        billing_service=billing_service,
        treatment_procedure_id=treatment_procedure_id,
        cost_breakdown_id=cost_breakdown_id,
        wallet_id=wallet_id,
        payor_type=models.PayorType.MEMBER,
        treatment_procedure_status=treatment_procedure_status,
    )
    stats.increment(
        metric_name="direct_payment.billing.tasks.rq_job_create_bill.member_bill",
        pod_name=stats.PodNames.BENEFITS_EXP,
    )

    log.info(
        "Completed member bill creation task.",
        treatment_procedure_id=str(treatment_procedure_id),
        cost_breakdown_id=str(cost_breakdown_id),
        wallet_id=str(wallet_id),
    )


@job("high_mem", service_ns="billing", team_ns="benefits_experience")
def create_and_process_member_refund_bills(
    treatment_procedure_id: int,
) -> None:
    """
    Temporary RQ job to create refund bills and process them as a background process. Will be replaced with pubsub.
    """
    log.info(
        "Starting member bill refund creation task.",
        treatment_procedure_id=treatment_procedure_id,
    )

    billing_service = BillingService(
        session=db.session,
        payment_gateway_base_url=(
            UNAUTHENTICATED_PAYMENT_SERVICE_URL
            if IS_INTEGRATIONS_K8S_CLUSTER
            else INTERNAL_TRUST_PAYMENT_GATEWAY_URL
        ),
    )

    bills_to_refund = (
        billing_service.compute_all_linked_paid_or_new_bill_and_trans_for_procedure(
            treatment_procedure_id
        )
    )

    payor_ids = {bill[0].payor_id for bill in bills_to_refund}
    if len(payor_ids) > 1:
        raise ValueError(
            f"Bills have more than one payor id:{payor_ids} - this should never happen "
        )
    refund_bills = _create_and_persist_refund_bills(billing_service, bills_to_refund)
    everything = list(zip(refund_bills, bills_to_refund))
    no_of_refunds = len(everything)
    log.info(f"Created {no_of_refunds} refund bill(s).")
    for i, (refund_bill, (bill_to_refund, bpr)) in enumerate(everything):
        # In case of an error, log an keep continuing to process
        try:
            log.info(
                f"Processing bill {i + 1} of {no_of_refunds}",
                bill_to_refund_id=str(bill_to_refund.id),
                bill_to_refund_uuid=str(bill_to_refund.uuid),
                refund_bill_uuid=refund_bill.uuid,
                refund_bill_id=str(refund_bill.id),
            )
            # load the version that was persisted into the DB
            refund_bill = billing_service.get_bill_by_uuid(refund_bill.uuid)
            _ = billing_service.set_new_refund_or_reverse_bill_to_processing(
                refund_or_reverse_transfer_bill=refund_bill,
                linked_bill=bill_to_refund,
                linked_bill_pr=bpr,
                attempt_count=1,
                initiated_by="rq_create_and_process_member_refund_bills",
                headers=None,
            )
        except Exception:
            log.error(
                "Retry for bill did not succeed.",
                refund_bill=refund_bill.uuid,
                linked_bill=bill_to_refund.uuid,
                reason=format_exc(),
            )
    log.info("Cancelling estimates for procedure", procedure_id=treatment_procedure_id)
    billing_service.cancel_member_estimates_for_procedures_without_commit(
        procedure_ids=[treatment_procedure_id]
    )
    billing_service.session.commit()


@job(service_ns="billing", team_ns="benefits_experience")
def from_clinic_reverse_transfer_bill_create_member_employer_bill_and_process(
    *, clinic_bill_id: int
) -> int:
    try:
        billing_service = BillingService(
            session=db.session,
            payment_gateway_base_url=(
                UNAUTHENTICATED_PAYMENT_SERVICE_URL
                if IS_INTEGRATIONS_K8S_CLUSTER
                else INTERNAL_TRUST_PAYMENT_GATEWAY_URL
            ),
        )
        clinic_bill = billing_service.get_bill_by_id(clinic_bill_id)
        _create_and_process_member_employer_refund_bills(
            billing_service=billing_service,
            clinic_bill=clinic_bill,  # type: ignore[arg-type] # Argument "clinic_bill" to "_create_and_process_member_employer_refund_bills" has incompatible type "Optional[Bill]"; expected "Bill"
        )
        return 0
    except Exception:
        log.error(
            "Unable to create and/or process member and employer refund bills from clinic bill",
            input_bill=clinic_bill_id,
            reason=format_exc(),
        )
    return 1  # Failure


def _create_and_process_member_employer_refund_bills(
    billing_service: BillingService,
    clinic_bill: Bill,
) -> List[Bill]:
    refund_bills: list[Bill] = []
    for payor_type in {PayorType.MEMBER, PayorType.EMPLOYER}:
        refund_bills += billing_service.create_full_refund_bills_for_payor(
            procedure_id=clinic_bill.procedure_id, payor_type=payor_type
        )
    billing_service.session.commit()

    for refund_bill in refund_bills:
        if (
            refund_bill.payor_type != PayorType.EMPLOYER
            or can_employer_bill_be_auto_processed(refund_bill)
        ):
            log.info(
                "Refund bill - submitted for processing.",
                refund_bill_id=str(refund_bill.id),
                refund_bill_uuid_id=str(refund_bill.id),
                refund_bill_payor_type=str(refund_bill.payor_type),
            )
            billing_service.set_new_bill_to_processing(refund_bill)
        else:
            log.info(
                "Refund bill - ignored for processing.",
                refund_bill_id=str(refund_bill.id),
                refund_bill_uuid_id=str(refund_bill.id),
                refund_bill_payor_type=str(refund_bill.payor_type),
            )
    return refund_bills


def _create_and_persist_refund_bills(billing_service, bills_to_refund):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # creating the refund bills
    refund_bills = [
        billing_service.create_full_refund_bill_from_bill(bill_to_refund, bpr)
        for (bill_to_refund, bpr) in bills_to_refund
    ]
    # persist the refund bills
    billing_service.session.commit()
    return refund_bills


def _create_employer_bill(
    treatment_procedure_id: int, cost_breakdown_id: int, wallet_id: int
) -> None:
    log.info(
        "Starting employer bill creation task.",
        treatment_procedure_id=str(treatment_procedure_id),
        cost_breakdown_id=str(cost_breakdown_id),
        wallet_id=str(wallet_id),
    )
    billing_service = BillingService(
        session=db.session,
        payment_gateway_base_url=(
            UNAUTHENTICATED_PAYMENT_SERVICE_URL
            if IS_INTEGRATIONS_K8S_CLUSTER
            else INTERNAL_TRUST_PAYMENT_GATEWAY_URL
        ),
    )
    bill = _create_bill(
        billing_service=billing_service,
        treatment_procedure_id=treatment_procedure_id,
        cost_breakdown_id=cost_breakdown_id,
        wallet_id=wallet_id,
        payor_type=models.PayorType.EMPLOYER,
        treatment_procedure_status=TreatmentProcedureStatus.COMPLETED,
        # employer bills are only created on treatment completion
    )
    stats.increment(
        metric_name="direct_payment.billing.tasks.rq_job_create_bill.employer_bill",
        pod_name=stats.PodNames.BENEFITS_EXP,
    )
    if bill:
        log.info(
            "Created employer bill.",
            bill_id=str(bill.id),
            bill_uuid=str(bill.uuid),
            bill_amount=bill.amount,
        )
        if can_employer_bill_be_auto_processed(bill):
            log.info(
                "Created employer bill that will be auto processed.",
                bill_id=str(bill.id),
                bill_uuid=str(bill.uuid),
                bill_amount=bill.amount,
            )
            bill = billing_service.set_new_bill_to_processing(input_bill=bill)
        else:
            log.info(
                "Created employer bill that will not be auto processed.",
                bill_id=str(bill.id),
                bill_uuid=str(bill.uuid),
                bill_amount=bill.amount,
            )

        # if the employer bill amount is < the min allowed by stripe> - it will be PAID, so immediately spawn out the
        # clinic bill. This is not a refund flow and so we do not check for Refunded Bill status
        if bill.status == BillStatus.PAID:
            log.info(
                "Creating clinic bill from employer bill",
                bill_uuid=str(bill.uuid),
                bill_amount=bill.amount,
            )
            from_employer_bill_create_clinic_bill_and_process(emp_bill_id=bill.id)

    log.info(
        "Completed employer bill creation task.",
        treatment_procedure_id=str(treatment_procedure_id),
        cost_breakdown_id=str(cost_breakdown_id),
        wallet_id=str(wallet_id),
    )


def _create_bill(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    billing_service: BillingService,
    treatment_procedure_id: int,
    cost_breakdown_id: int,
    wallet_id: int,
    payor_type: PayorType,
    treatment_procedure_status: TreatmentProcedureStatus,
):
    cost_breakdown = _get_cost_breakdown(cost_breakdown_id)
    procedure = _get_procedure(treatment_procedure_id)
    payor = _get_payor_from_wallet(wallet_id, payor_type)

    log.info(
        "Calculating amount for new bill.",
        payor_type=payor_type.value,
        payor_id=str(payor.id),
        treatment_procedure_id=str(treatment_procedure_id),
        cost_breakdown_id=str(cost_breakdown_id),
    )
    payor_responsibility = _get_responsibility_by_payor(cost_breakdown, payor_type)
    (
        amount,
        past_amount,
    ) = billing_service.calculate_new_and_past_bill_amount_from_new_responsibility(
        payor_id=payor.id,
        payor_type=payor_type,
        procedure_id=treatment_procedure_id,
        new_responsibility=payor_responsibility,
    )
    if payor_type == PayorType.MEMBER:
        log.info("Attempting to create member bill or estimate.")
        member_bill_info = billing_service.handle_member_billing_for_procedure(
            delta=amount,  # type: ignore[arg-type] # Argument "delta" to "handle_member_billing_for_procedure" of "BillingService" has incompatible type "Optional[int]"; expected "int"
            payor_id=payor.id,
            procedure_id=treatment_procedure_id,
            procedure_name=procedure.procedure_name,
            cost_breakdown_id=cost_breakdown_id,
            treatment_procedure_status=treatment_procedure_status.value,
        )
        if member_bill_info.should_caller_commit:
            billing_service.session.commit()
        (
            clinic_name,
            clinic_location,
        ) = _get_clinic_name_and_location_strings(procedure_id=procedure.id)
        if member_bill_info.bill:
            log.info(
                "Bill created.",
                bill_uuid=member_bill_info.bill.uuid,
                payor_type=payor_type.value,
                payor_id=str(payor.id),
                treatment_procedure_id=str(treatment_procedure_id),
                cost_breakdown_id=str(cost_breakdown_id),
            )
            if member_bill_info.should_caller_notify_of_bill:
                _notify(
                    payor_type=payor_type,
                    treatment_procedure_status=treatment_procedure_status,
                    bill=member_bill_info.bill,
                    past_amount=past_amount,
                    payor_responsibility=payor_responsibility,
                    clinic_name=clinic_name,
                    clinic_location=clinic_location,
                )
        if member_bill_info.estimate:
            log.info(
                "Estimate created.",
                bill_uuid=member_bill_info.estimate.uuid,
                payor_type=payor_type.value,
                payor_id=str(payor.id),
                treatment_procedure_id=str(treatment_procedure_id),
                cost_breakdown_id=str(cost_breakdown_id),
            )
            _notify_ephemeral(
                payor_type=payor_type,
                treatment_procedure_status=treatment_procedure_status.value,
                bill=member_bill_info.estimate,
                payor_responsibility=format_cents_to_usd_str(
                    member_bill_info.estimate.amount
                ),
                total_cost=format_cents_to_usd_str(procedure.cost),
                maven_benefit=format_cents_to_usd_str(
                    cost_breakdown.total_employer_responsibility
                ),
                credits_used=procedure.cost_credit,  # type: ignore[arg-type] # Argument "credits_used" to "_notify_ephemeral" has incompatible type "Optional[int]"; expected "int"
                clinic_location=clinic_location,
                clinic_name=clinic_name,
                treatment_procedure_name=procedure.procedure_name,
            )
        if not member_bill_info.bill and not member_bill_info.estimate:
            log.info(
                "No member bill or estimate created - pre-existing bills and delta with sum(pre-existing bills) is 0.",
                payor_type=payor_type,
                payor_id=str(payor.id),
                treatment_procedure_id=str(treatment_procedure_id),
                cost_breakdown_id=str(cost_breakdown_id),
            )
    elif amount is not None:
        log.info("Attempting to create bill.")
        bill = billing_service.create_bill(
            label=procedure.procedure_name,
            amount=amount,
            payor_type=payor_type,
            payor_id=payor.id,
            treatment_procedure_id=procedure.id,
            cost_breakdown_id=cost_breakdown_id,
            payment_method=models.PaymentMethod.PAYMENT_GATEWAY,
        )
        billing_service.session.commit()
        log.info(
            "Bill created.",
            bill_uuid=bill.uuid,
            payor_type=payor_type.value,
            payor_id=str(payor.id),
            treatment_procedure_id=str(treatment_procedure_id),
            cost_breakdown_id=str(cost_breakdown_id),
        )
        bill = billing_service.get_bill_by_uuid(str(bill.uuid))  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[Bill]", variable has type "Bill")
        _notify(
            payor_type,
            treatment_procedure_status,
            bill,
            past_amount,
            payor_responsibility,
        )
        return bill
    else:
        log.info(
            "Bill not created - pre-existing bills and delta with sum(pre-existing bills) is 0.",
            payor_type=payor_type,
            payor_id=str(payor.id),
            treatment_procedure_id=str(treatment_procedure_id),
            cost_breakdown_id=str(cost_breakdown_id),
        )


def _notify_ephemeral(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    payor_type: PayorType,
    treatment_procedure_status: str,
    bill: Bill,
    payor_responsibility: str,
    total_cost: str,
    maven_benefit: str,
    credits_used: int,
    treatment_procedure_name: str,
    clinic_location: str,
    clinic_name: str,
) -> None:
    if (
        payor_type == PayorType.MEMBER
        and treatment_procedure_status == "SCHEDULED"
        and bill.is_ephemeral
        and bill.status == BillStatus.NEW
    ):
        log.info(
            "Sending notification for estimate.",
            bill_id=str(bill.id),
            bill_uuid=str(bill.uuid),
        )
        try:
            event_properties = {
                "bill_uuid": str(bill.uuid),
                "benefit_id": get_benefit_id_from_wallet_id(bill.payor_id),
                "total_cost": total_cost,
                "member_responsibility": payor_responsibility,
                "maven_benefit": maven_benefit,
                "credits_used": f"{credits_used or 0} credit{'s' if credits_used != 1 else ''}",
                "procedure_name": treatment_procedure_name,
                "clinic_name": clinic_name,
                "clinic_location": clinic_location,
            }
            event_name = "mmb_billing_estimate"
            if event_name:
                log.info(
                    "Asynch sending notification.",
                    bill_id=str(bill.id),
                    bill_uuid=str(bill.uuid),
                    user_id=str(bill.payor_id),
                    event_name=event_name,
                )
                send_notification_event.delay(
                    user_id=str(bill.payor_id),
                    user_id_type="PAYOR_ID",
                    user_type="MEMBER",
                    event_source_system="BILLING",
                    event_name=event_name,
                    event_properties=event_properties,
                )
        except Exception:
            log.error(
                "Send Notification Failure.",
                bill_id=str(bill.id),
                bill_uuid=str(bill.uuid),
                user_id=str(bill.payor_id),
                reason=format_exc(),
            )
    else:
        log.error(
            "Estimate bill is in corrupted state and unable to send notification",
            bill_uuid=bill.uuid,
            bill_status=bill.status,
            is_ephemeral=bill.is_ephemeral,
        )


def _notify(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    payor_type: PayorType,
    treatment_procedure_status,
    bill: Bill,
    past_amount: int,
    payor_responsibility: int,
    clinic_name: str = "",
    clinic_location: str = "",
) -> None:
    if payor_type == PayorType.MEMBER and treatment_procedure_status in {
        TreatmentProcedureStatus.COMPLETED,
        TreatmentProcedureStatus.PARTIALLY_COMPLETED,
        TreatmentProcedureStatus.SCHEDULED,
    }:
        log.info(
            "Sending notification for bill.",
            bill_id=str(bill.id),
            bill_uuid=str(bill.uuid),
        )
        try:
            event_properties = {
                "benefit_id": get_benefit_id_from_wallet_id(bill.payor_id),
                "payment_amount": f"${payor_responsibility / 100:,.2f}",
                "payment_method_type": (
                    bill.payment_method_type.value if bill.payment_method_type else ""
                ),
                "payment_method_last4": (
                    bill.payment_method_label if bill.payment_method_label else ""
                ),
            }
            event_name = ""
            # the refund flow will never create a 0 cost bill, but the charge flow might.
            if bill.amount < 0:
                log.info(
                    "Notifications for refund bills are generated during bill processing.",
                    bill_uuid=str(bill.uuid),
                    bill_id=str(bill.id),
                )
            elif bill.amount >= 0:
                if (
                    treatment_procedure_status == TreatmentProcedureStatus.SCHEDULED
                    or (
                        treatment_procedure_status == TreatmentProcedureStatus.COMPLETED
                        and not past_amount
                    )
                ):
                    if bill.amount > 0:
                        event_name = "mmb_upcoming_payment_reminder"
                        # payment amount is the amount to be paid by member if this is not an adjustment.
                        event_properties[
                            "payment_amount"
                        ] = f"${(bill.amount + bill.last_calculated_fee) / 100:,.2f}"
                        event_properties["clinic_location"] = clinic_location
                        event_properties["clinic_name"] = clinic_name
                else:
                    event_name = "mmb_payment_adjusted_addl_charge"
                    event_properties[
                        "original_payment_amount"
                    ] = f"${past_amount / 100:,.2f}"
                    event_properties[
                        "additional_charge_amount"
                    ] = f"${(bill.amount + bill.last_calculated_fee) / 100:,.2f}"

                event_properties[
                    "payment_date"
                ] = bill.processing_scheduled_at_or_after.isoformat(  # type: ignore[union-attr] # Item "None" of "Optional[datetime]" has no attribute "isoformat"
                    "T", "milliseconds"
                ).replace(
                    ".000", ":000Z"
                )
            if event_name:
                log.info(
                    "Asynch sending notification.",
                    bill_id=str(bill.id),
                    bill_uuid=str(bill.uuid),
                    user_id=str(bill.payor_id),
                    event_name=event_name,
                )
                send_notification_event.delay(
                    user_id=str(bill.payor_id),
                    user_id_type="PAYOR_ID",
                    user_type="MEMBER",
                    event_source_system="BILLING",
                    event_name=event_name,
                    event_properties=event_properties,
                )
        except Exception:
            log.error(
                "Send Notification Failure.",
                bill_id=str(bill.id),
                bill_uuid=str(bill.uuid),
                user_id=str(bill.payor_id),
                reason=format_exc(),
            )


def _get_responsibility_by_payor(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    cost_breakdown: CostBreakdown, payor_type: models.PayorType
):
    if payor_type == models.PayorType.MEMBER:
        return cost_breakdown.total_member_responsibility
    if payor_type == models.PayorType.EMPLOYER:
        return cost_breakdown.total_employer_responsibility
    raise ValueError(
        "Attempted to create a bill for an undefined Payor Type in rq_job_create_bill."
    )


# TODO: add validation errors
def _get_customer_payment_info(customer_id: str) -> str:
    gateway_client = get_client(INTERNAL_TRUST_PAYMENT_GATEWAY_URL)  # type: ignore[arg-type] # Argument 1 to "get_client" has incompatible type "Optional[str]"; expected "str"
    customer = gateway_client.get_customer(customer_id)
    return customer.payment_methods[0].last4


def _get_procedure(procedure_id: int) -> TreatmentProcedure:
    procedure_repo = TreatmentProcedureRepository(db.session)
    procedure = procedure_repo.read(treatment_procedure_id=procedure_id)
    return procedure


def _get_cost_breakdown(cost_breakdown_id: int) -> CostBreakdown:
    cost_breakdown = CostBreakdown.query.get(cost_breakdown_id)
    return cost_breakdown


def _get_payor_from_wallet(wallet_id: int, payor_type: models.PayorType):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if payor_type == models.PayorType.MEMBER:
        return _get_member(wallet_id)
    if payor_type == models.PayorType.EMPLOYER:
        return _get_employer(wallet_id)
    raise ValueError(
        "Attempted to create a bill for an undefined Payor Type in rq_job_create_bill."
    )


def _get_member(wallet_id: int) -> ReimbursementWallet:
    wallet = ReimbursementWallet.query.get(wallet_id)
    if not wallet:
        raise ValueError("Invalid wallet id provided to bill.")
    return wallet


def _get_clinic_name_and_location_strings(procedure_id: int) -> Tuple[str, str]:
    clinic = get_clinic_locations_as_dicts_from_treatment_procedure_id(
        treatment_procedure_id=procedure_id
    )
    if not clinic:
        return "", ""
    subdivision_code = clinic["subdivision_code"]
    clinic_state = (
        subdivision_code.split("-")[1] if len(subdivision_code.split("-")) == 2 else ""
    )
    return clinic["name"], f"{clinic['city']}, {clinic_state}"


def format_cents_to_usd_str(cents: int) -> str:
    return f"${Decimal(cents) / 100:,.2f}"


def _get_employer(wallet_id: int) -> ReimbursementOrganizationSettings:
    org_setting = (
        ReimbursementOrganizationSettings.query.join(
            ReimbursementWallet,
            ReimbursementWallet.reimbursement_organization_settings_id
            == ReimbursementOrganizationSettings.id,
        )
        .filter(ReimbursementWallet.id == wallet_id)
        .first()
    )
    if not org_setting:
        raise ValueError(
            "Invalid wallet id provided to bill. Could not retrieve ReimbursementOrganizationSettings."
        )
    return org_setting
