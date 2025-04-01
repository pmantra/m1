from decimal import Decimal
from typing import Tuple

from appointments.models.payments import Credit
from utils.log import logger

log = logger(__name__)


# This method split one credit into two and returns both:
# credit:  contains credit to be used
# new_credit:  contains remaining credit
def split_credit(
    credit: Credit,
    updated_credit_amount: Decimal,
) -> Tuple[Credit, Credit]:
    """
    Splits `credit` into two credits.
    return[0] is `credit` with `credit.amount=updated_credit_amount`
    return[1] is a new Credit with the remaining balance.
    """
    log.debug("Splitting %s into new and old credits", credit)
    if updated_credit_amount <= 0:
        log.error("Unexpected function call to split credit into non-positive value")
        raise ValueError("Credits must be positive")
    elif updated_credit_amount >= credit.amount:
        log.error("Must split credit into smaller amount")
        raise ValueError("Cannot split credit into larger value")

    excess = credit.amount - updated_credit_amount
    new_credit = credit.copy_with_excess(excess)
    credit.amount = updated_credit_amount

    return credit, new_credit
