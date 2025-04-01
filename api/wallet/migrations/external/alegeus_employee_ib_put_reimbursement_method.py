from requests import Response

from app import create_app
from utils.log import logger
from wallet.alegeus_api import AlegeusApi
from wallet.migrations.external.alegeus_employee_edi_transfer import (
    get_all_alegeus_user_wallets,
)

log = logger(__name__)

if __name__ == "__main__":
    with create_app().app_context():
        all_alegeus_wallets = get_all_alegeus_user_wallets()
        alegeus_api = AlegeusApi()

        total_wallets = len(all_alegeus_wallets)
        wallets_failed = 0

        log.info(f"{total_wallets} wallets to update")

        banking_info = {
            "BankAcctName": "Test Checking",
            "BankAccount": "0037308343",
            "BankAccountTypeCode": "1",
            "BankRoutingNumber": "064000017",
        }

        for wallet in all_alegeus_wallets:
            try:
                response: Response = alegeus_api.get_employee_demographic(wallet)

                if response.status_code == 200:
                    alegeus_api.put_employee_services_and_banking(wallet, banking_info)
                else:
                    log.warning(
                        f"Wallet ID: {wallet.id} has not been configured in WCA"
                    )
                    wallets_failed += 1
            except Exception as e:
                log.error("Something went wrong", exception=e, wallet_id=wallet.id)
                wallets_failed += 1

        log.info(
            f"Updated {total_wallets - wallets_failed} wallets out of {total_wallets} for Alegeus"
        )
