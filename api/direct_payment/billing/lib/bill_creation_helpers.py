from __future__ import annotations

import datetime

from common import stats
from direct_payment.billing import models
from direct_payment.billing.constants import MEMBER_BILLING_OFFSET_DAYS
from direct_payment.billing.lib.legacy_mono import (
    get_org_invoicing_settings_as_dict_from_ros_id,
    get_treatment_procedure_as_dict_from_id,
)
from direct_payment.billing.models import CardFunding, PaymentMethodType, PayorType
from utils.log import logger

log = logger(__name__)


def _get_procedure_status(treatment_procedure_id: int) -> str | None:
    to_return = None
    proc = get_treatment_procedure_as_dict_from_id(treatment_procedure_id)
    if proc and (proc_status := proc.get("status")):
        to_return = proc_status.value
    return to_return


def compute_processing_scheduled_at_or_after(
    payor_type: PayorType,
    amount: int,
    current_time: datetime.datetime,
    treatment_procedure_id: int | None,
    payor_id: int | None = None,
) -> datetime.datetime | None:
    """
    Calculates the processing_scheduled_at_or_after time that should be stamped on the bill. This is always the
    input current_time parameter for CLINIC and non-positive MEMBER Bill.
    For positive member bills, this
    is dependent on Treatment Procedure Status if the release-charge-on-tp-completion is TRUE, and is current_time +
    offset if the feature flag is False.
    For EMPLOYER bIlls - If the bill org is an org that used invoicing, an appropriate delay is applied otherwise the
    bills are set to process immediately.
    :param payor_id:
    :param payor_type: MEMBER, CLINIC or EMPLOYER
    :param amount: Signed amount on the bill
    :param current_time:The time at which this function is called
    :param treatment_procedure_id: The linked treatment procedure id (optional)
    :return: date time to be stamped on processing_scheduled_at_or_after. Can be null
    """
    tp_status = _get_procedure_status(treatment_procedure_id)  # type: ignore[arg-type] # Argument 1 to "_get_procedure_status" has incompatible type "Optional[int]"; expected "int"
    if payor_type == PayorType.MEMBER and amount == 0 and tp_status == "SCHEDULED":
        to_return = None
    elif payor_type == PayorType.MEMBER and amount > 0:
        # bills get a scheduled processing date only if the TP status is completed/partially completed
        to_return = (
            current_time + datetime.timedelta(days=MEMBER_BILLING_OFFSET_DAYS)
            if tp_status in {"COMPLETED", "PARTIALLY_COMPLETED"}
            else None
        )
    elif payor_type == PayorType.EMPLOYER:
        if not payor_id:
            raise ValueError(
                "Payor ID must be provided to compute processing_scheduled_at_or_after for Employee bills"
            )
        ois = get_org_invoicing_settings_as_dict_from_ros_id(payor_id)
        to_return = current_time + datetime.timedelta(
            days=ois.get("bill_processing_delay_days", 0)
        )

        if ois:
            stats.increment(
                metric_name="direct_payment.billing.apply_processing_delay",
                pod_name=stats.PodNames.BENEFITS_EXP,
                tags=[f"organization_id:{ois.get('organization_id', '')}"],
            )

    else:
        # CLINIC bills, and non-positive MEMBER bills for completed procedures are processed as soon as they are created
        to_return = current_time

    return to_return


def calculate_fee(
    payment_method: models.PaymentMethod,
    payment_method_type: PaymentMethodType,
    amount: int,
    card_funding: CardFunding = None,  # type: ignore[assignment] # Incompatible default for argument "card_funding" (default has type "None", argument has type "CardFunding")
) -> int:
    """
    Calculate fee. 3% of amount if payment method is PAYMENT_GATEWAY and payment method type is a card and funding
    type is prepaid, debit or unknown. Else 0.
    :param payment_method_type: The payment method type.
    :param payment_method: card or us bank account
    :param amount: The amount to calculate the fee on.(in pennies)
    :param card_funding: funding of card (debit, credit, prepaid or unknown)
    :return: the fee 0 - or 3% of the amount (rounded)
    """

    waive_fee = (
        payment_method != models.PaymentMethod.PAYMENT_GATEWAY
        or payment_method_type != PaymentMethodType.card
        or card_funding in (CardFunding.DEBIT, CardFunding.PREPAID, CardFunding.UNKNOWN)
    )

    if waive_fee:
        return 0
    to_return = round(0.03 * amount)
    return to_return
