from authn.models.user import User
from wallet.utils.alegeus.debit_cards.manage import remove_phone_number_from_alegeus


def remove_mobile_number(user: User, old_phone_number: str) -> bool:
    success = True
    # All wallets with debit cards should have existing phone numbers at
    # Alegeus unless previously removed
    for wallet in user.reimbursement_wallets:
        if len(wallet.debit_cards) > 0:
            # If removing by passing the old number proves too fragile, the more
            # blunt method would be to list all existing numbers at Alegeus and
            # remove each one individually.
            if old_phone_number is not None:
                success &= remove_phone_number_from_alegeus(wallet, old_phone_number)

    return success
