import datetime

from cost_breakdown.utils.helpers import get_cycle_based_wallet_balance_from_credit
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from utils.log import logger
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)


def get_currency_balance_from_credit_wallet_balance(
    treatment_procedure: TreatmentProcedure,
) -> int:
    # verify benefit type
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet_balance = get_cycle_based_wallet_balance_from_credit(
        wallet=wallet,
        category_id=treatment_procedure.reimbursement_request_category_id,
        cost_credit=treatment_procedure.cost_credit,  # type: ignore[arg-type] # Argument "cost_credit" to "get_cycle_based_wallet_balance_from_credit" has incompatible type "Optional[int]"; expected "int"
        cost=treatment_procedure.cost,
    )
    if wallet_balance is None:
        return 0
    return wallet_balance


# benefits expire the first day of the following month of the e9y end date
def calculate_benefits_expiration_date(
    eligibility_end_date: datetime.date,
) -> datetime.date:
    return (eligibility_end_date.replace(day=1) + datetime.timedelta(days=32)).replace(
        day=1
    )
