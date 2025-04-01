from datetime import date, datetime, timedelta
from traceback import format_exc

from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.lib import legacy_mono
from direct_payment.billing.models import BillProcessingRecord, BillStatus, PayorType
from utils.log import logger

log = logger(__name__)


def monitor_bills() -> bool:
    to_return = True
    try:
        cutoff_date = date.today() + timedelta(days=-4)
        monitor_stale_new_member_bills(cutoff_date)
        log.info(
            "Monitoring stale NEW member bills completed",
            cutoff_date=cutoff_date.strftime("%Y-%m-%d"),
        )
    except Exception as ex:
        log.error(
            "Error while monitoring stale NEW member bills",
            error=str(ex),
            reason=format_exc(),
        )
        to_return = False
    return to_return


def monitor_stale_new_member_bills(date_cutoff: date):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Logs the bill UUIDS created before the "date_cutoff 23:59:59" that are still in NEW state. Bills that do not have
    blocking refunds are logged at the highest of LogLevel.Error and the log_level parameter levels. Bills that do have
    blocking refunds are logged at the level of the log_level parameter
    :param date_cutoff:
    :type date:datetime.date
    :return: None
    :rtype:
    """
    billing_service = BillingService()
    without_refunds_uuids = set()
    with_refunds_uuids = set()
    if new_bills := billing_service.compute_new_member_bills(
        start_date=None, end_date=date_cutoff
    ):
        new_bills_uuids = {str(bill.uuid) for bill in new_bills}
        new_bills_without_refunds = billing_service.compute_new_member_bills_to_process(
            start_date=None, end_date=date_cutoff
        )
        without_refunds_uuids = {str(bill.uuid) for bill in new_bills_without_refunds}
        with_refunds_uuids = new_bills_uuids - without_refunds_uuids
    date_cutoff_str = datetime.combine(date_cutoff, datetime.max.time()).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    if without_refunds_uuids:
        log.error(
            "There are NEW member bills (WITHOUT refunds associated with the member) created earlier than the cutoff",
            date_cutoff=date_cutoff_str,
            bill_count=len(without_refunds_uuids),
            uuids=", ".join(without_refunds_uuids),
        )
    if with_refunds_uuids:
        log.warning(
            "There are NEW member bills (WITH refunds associated with the member) created earlier than the cutoff",
            date_cutoff=date_cutoff_str,
            bill_count=len(with_refunds_uuids),
            uuids=", ".join(with_refunds_uuids),
        )


def monitor_failed_bills() -> bool:
    to_return = True
    try:
        billing_service = BillingService()
        payor_types = list(PayorType.__reversed__())
        pt_to_bill_dict = {pt: [] for pt in payor_types}
        bills = sorted(
            billing_service.get_by_payor_types_statuses(
                payor_types, [BillStatus.FAILED]
            ),
            key=lambda b: b.created_at,  # type: ignore[arg-type,return-value] # Argument "key" to "sorted" has incompatible type "Callable[[Bill], Optional[datetime]]"; expected "Callable[[Bill], Union[SupportsDunderLT[Any], SupportsDunderGT[Any]]]" #type: ignore[return-value] # Incompatible return value type (got "Optional[datetime]", expected "Union[SupportsDunderLT[Any], SupportsDunderGT[Any]]")
            reverse=True,
        )
        bill_ids = [b.id for b in bills]
        bpr_dict = billing_service.get_latest_records_with_specified_statuses_for_bill_ids(
            bill_ids, [BillStatus.FAILED]  # type: ignore[arg-type] # Argument 1 to "get_latest_records_with_specified_statuses_for_bill_ids" of "BillingService" has incompatible type "List[Optional[int]]"; expected "List[int]"
        )

        for bill in bills:
            pt_to_bill_dict[bill.payor_type].append(bill)

        for payor_type in payor_types:
            pt_bills = pt_to_bill_dict[payor_type]
            if pt_bills:
                fail_reasons = [""]
                for bill in pt_bills:
                    # BPRS can be messy when people mess around with bills in admin
                    bpr: BillProcessingRecord = bpr_dict.get(bill.id)  # type: ignore[assignment,arg-type] # Incompatible types in assignment (expression has type "Optional[BillProcessingRecord]", variable has type "BillProcessingRecord") #type: ignore[arg-type] # Argument 1 to "get" of "dict" has incompatible type "Optional[int]"; expected "int"
                    ep = bpr.body.get("error_payload", {}) if bpr and bpr.body else {}
                    decline_code = ep.get("decline_code", "")
                    msg = ep.get("error_detail", {}).get("message", "")
                    error = bpr.body.get("error", "") if bpr and bpr.body else ""
                    fail_reasons.append(
                        f"bill_id: {bill.id} created_at: {bill.created_at} failed_at: {bill.failed_at} error_type: "
                        f"{bill.error_type}, error: {error}, decline_code: {decline_code}, message: {msg}"
                    )
                bill_failed_ids = ", ".join(str(bill.id) for bill in pt_bills)
                bill_failed_details = " \n ".join(fail_reasons)
                log.info(
                    "Bill Monitoring: Failed bills by payor type.",
                    bill_payor_type=payor_type.value,
                    bill_failed_count=len(pt_bills),
                    bill_failed_details=bill_failed_details,
                    bill_failed_ids=bill_failed_ids,
                )
    except Exception as ex:
        log.error(
            "Error while monitoring for FAILED bills",
            error=str(ex),
            reason=format_exc(),
        )
        to_return = False
    return to_return


def monitor_bills_scheduled_tps() -> bool:
    to_return = True
    try:
        log.info("Monitoring billing for scheduled treatment procedures")
        scheduled_tps = legacy_mono.get_treatment_procedure_ids_with_status_since_bill_timing_change(
            statuses=["SCHEDULED"]
        )
        billing_service = BillingService()
        scheduled_with_estimates = (
            billing_service.get_procedure_ids_with_estimates_or_bills(
                procedure_ids=scheduled_tps, is_ephemeral=True
            )
        )
        scheduled_with_bills = (
            billing_service.get_procedure_ids_with_estimates_or_bills(
                procedure_ids=scheduled_tps, is_ephemeral=False
            )
        )
        scheduled_tps_missing_estimates = set(scheduled_tps) - set(
            scheduled_with_estimates
        )
        if scheduled_with_bills or scheduled_tps_missing_estimates:
            log.error(
                "Scheduled treatment procedures with incorrect billing state",
                procedures_missing_estimates=scheduled_tps_missing_estimates,
                procedures_with_bills=scheduled_with_bills,
            )
        else:
            log.info(
                "No scheduled treatment procedures with bills or missing estimates"
            )
    except Exception as ex:
        log.error(
            "Error while monitoring billing for scheduled treatment procedures",
            error=str(ex),
            reason=format_exc(),
        )
        to_return = False
    return to_return


def monitor_bills_completed_tps() -> bool:
    to_return = True
    try:
        log.info("Monitoring billing for completed treatment procedures")
        completed_tps = legacy_mono.get_treatment_procedure_ids_with_status_since_bill_timing_change(
            statuses=["COMPLETED", "PARTIALLY_COMPLETED"]
        )
        billing_service = BillingService()
        completed_with_estimates = (
            billing_service.get_procedure_ids_with_estimates_or_bills(
                procedure_ids=completed_tps, is_ephemeral=True
            )
        )
        completed_with_bills = (
            billing_service.get_procedure_ids_with_estimates_or_bills(
                procedure_ids=completed_tps, is_ephemeral=False
            )
        )
        completed_missing_bills = set(completed_tps) - set(completed_with_bills)
        if completed_with_estimates or completed_missing_bills:
            log.error(
                "Completed treatment procedures with incorrect billing state",
                procedures_missing_bills=completed_missing_bills,
                procedures_with_estimatess=completed_with_estimates,
            )
        else:
            log.info(
                "No completed treatment procedures with estimates or missing bills"
            )
    except Exception as ex:
        log.error(
            "Error while monitoring billing for completed treatment procedures",
            error=str(ex),
            reason=format_exc(),
        )
        to_return = False
    return to_return
