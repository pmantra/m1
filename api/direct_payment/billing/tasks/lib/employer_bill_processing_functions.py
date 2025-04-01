from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytz

from common import stats
from direct_payment.billing.constants import INVOICED_ORGS_PILOT
from direct_payment.billing.lib.legacy_mono import (
    get_org_invoicing_settings_as_dict_from_ros_id,
    get_organisation_id_from_ros_id,
)
from direct_payment.billing.models import Bill, PayorType
from utils.log import logger

log = logger(__name__)


def can_employer_bill_be_auto_processed(bill: Bill) -> bool:
    res_val, res_reason = _can_employer_bill_be_auto_processed(bill)

    if res_val:
        # invoiced bills should always be blocked, but save on a db call by doing this only if needed
        if get_org_invoicing_settings_as_dict_from_ros_id(bill.payor_id):
            res_val, res_reason = (
                False,
                "This bill is linked to an invoiced organisation and cannot be auto-processed.",
            )

        # fallback during burn in period.
        if (
            org_id := get_organisation_id_from_ros_id(bill.payor_id)
        ) in INVOICED_ORGS_PILOT:
            log.warn(
                "An invoiced bill was caught by the org pilot fall back and forced to delay. Please investigate.",
                bill_id=str(bill.id),
                bill_uuid=str(bill.uuid),
                payor_id=str(bill.payor_id),
                organization_id=str(org_id),
                processing_scheduled_at_or_after=str(
                    bill.processing_scheduled_at_or_after
                ),
            )
            res_val, res_reason = (
                False,
                "The org id on the bill is in the INVOICED_ORGS_PILOT list and the bill was force delayed.",
            )

    log.info(
        "Can employer bill be auto-processed?",
        bill_id=str(bill.id),
        bill_uuid=str(bill.uuid),
        bill_can_be_auto_processed=res_val,
        reason=res_reason,
        bill_processing_scheduled_at_or_after=str(
            bill.processing_scheduled_at_or_after
        ),
    )
    stats.increment(
        metric_name="direct_payment.billing.tasks.rq_job_create_bill.can_employer_bill_be_auto_processed.",
        pod_name=stats.PodNames.BENEFITS_EXP,
        tags=[
            f"auto_processed_employer_bill:{res_val}",
            f"reimbursement_organisation_settings_id: {'NOT_RECORDED' if res_val else bill.payor_id}",
        ],
    )
    return res_val


def can_employer_bill_be_processed(bill: Bill) -> bool:
    res_val, res_reason = _can_employer_bill_be_auto_processed(bill)
    log.info(
        "Can employer bill be processed (no invoice linked blockages enforced)?",
        bill_id=str(bill.id),
        bill_uuid=str(bill.uuid),
        bill_can_be_processed=res_val,
        reason=res_reason,
        bill_processing_scheduled_at_or_after=str(
            bill.processing_scheduled_at_or_after
        ),
    )
    stats.increment(
        metric_name="direct_payment.billing.tasks.rq_job_create_bill.can_employer_bill_be_auto_processed.",
        pod_name=stats.PodNames.BENEFITS_EXP,
        tags=[
            f"auto_processed_employer_bill:{res_val}",
            f"reimbursement_organisation_settings_id: {'NOT_RECORDED' if res_val else bill.payor_id}",
        ],
    )
    return res_val


def _can_employer_bill_be_auto_processed(bill: Bill) -> tuple[bool, str]:
    if bill.payor_type != PayorType.EMPLOYER:
        log.error(
            "This function can only be invoked for Employer bills.",
            bill_id=str(bill.id),
            bill_uuid=str(bill.uuid),
            bill_payor_type=str(bill.payor_type),
        )
        raise ValueError()

    if not bill.processing_scheduled_at_or_after:
        return False, "processing_scheduled_at_or_after was not populated on the bill."

    # Get the current UTC time and round up to the nearest second. DB has a granularity of seconds and rounds up, so
    # we want the same behaviour for the now time (which has granularity of micro seconds) used for comparison.
    rounded_up_utc = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(
        seconds=1
    )
    # handle time zone if missing. everything is UTC always
    psoa = (
        pytz.utc.localize(bill.processing_scheduled_at_or_after)
        if not bill.processing_scheduled_at_or_after.tzinfo
        else bill.processing_scheduled_at_or_after
    )
    if psoa > rounded_up_utc:
        return (
            False,
            f"Processing_scheduled_at_or_after {psoa} on the bill is in the future. current time: {rounded_up_utc}",
        )

    return True, "The bill passed all auto processing checks."
