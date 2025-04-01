import datetime
from typing import Optional, Tuple

from direct_payment.treatment_procedure.utils.procedure_utils import (
    calculate_benefits_expiration_date,
)
from eligibility import e9y
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.utils.alegeus.enrollments.enroll_wallet import (
    get_eligibility_date_from_wallet,
)


def get_benefit_e9y_start_and_expiration_date(
    wallet: ReimbursementWallet, user_id: int
) -> Tuple[Optional[datetime.date], Optional[datetime.date]]:

    member_eligibility_start_date = None
    benefit_expires_date = None

    wallet_enablement = e9y.grpc_service.wallet_enablement_by_user_id_search(
        user_id=user_id,
    )
    if wallet_enablement:
        member_eligibility_start_date = get_eligibility_date_from_wallet(
            wallet, wallet_enablement
        )
        benefit_end_date = wallet_enablement.eligibility_end_date
        benefit_expires_date = (
            calculate_benefits_expiration_date(benefit_end_date)
            if benefit_end_date
            else None
        )
    return member_eligibility_start_date, benefit_expires_date
