from typing import Optional

from maven import feature_flags

from direct_payment.billing.constants import (
    CONFIGURE_BILLING_ABS_AUTO_PROCESS_MAX_AMOUNT,
)


def get_auto_process_max_amount() -> int:
    # pulled out for mocking
    return feature_flags.int_variation(
        CONFIGURE_BILLING_ABS_AUTO_PROCESS_MAX_AMOUNT, default=0
    )


def is_amount_too_small_for_payment_gateway(
    bill_amount: int, auto_process_max_amount: Optional[int] = None
) -> bool:
    if auto_process_max_amount is None:
        return abs(bill_amount) <= get_auto_process_max_amount()

    return abs(bill_amount) <= auto_process_max_amount
