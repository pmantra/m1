from random import randint

import luhn

from storage.connection import db
from wallet.models.reimbursement_wallet_benefit import ReimbursementWalletBenefit


def generate_wallet_benefit() -> ReimbursementWalletBenefit:
    rand = randint(10, 99)

    wallet_benefit = ReimbursementWalletBenefit(rand=rand)
    db.session.add(wallet_benefit)
    db.session.flush()

    base_benefit_id = str(rand) + str(wallet_benefit.incremental_id)
    checksum = str(luhn.generate(base_benefit_id))
    benefit_id = base_benefit_id + checksum
    wallet_benefit.checksum = checksum  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", variable has type "Optional[int]")
    wallet_benefit.maven_benefit_id = benefit_id
    db.session.add(wallet_benefit)

    return wallet_benefit
