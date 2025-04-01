from app import create_app
from storage.connection import db
from utils.log import logger
from wallet.alegeus_api import AlegeusApi
from wallet.migrations.external.alegeus_employee_edi_transfer import (
    get_all_alegeus_user_wallets,
)
from wallet.models.constants import ReimbursementAccountStatus
from wallet.models.reimbursement import (
    ReimbursementAccount,
    ReimbursementAccountType,
    ReimbursementPlan,
)

log = logger(__name__)

if __name__ == "__main__":
    with create_app().app_context():
        alegeus_api = AlegeusApi()

        # Get all qualified wallets
        qualified_wallets = get_all_alegeus_user_wallets()
        total_wallets = len(qualified_wallets)
        wallets_failed = 0

        log.info(f"{total_wallets} wallets to update")

        # For each wallet, verify that the info is in Alegeus WCA
        for wallet in qualified_wallets:

            # If the wallet is in Alegeus WCA, get the account info
            try:
                log.info("Getting account summary", wallet_id=wallet.id)
                response = alegeus_api.get_account_summary(wallet)

                if response.status_code == 200:
                    # Create a new ReimbursementAccount for each account in the response
                    resp_json = response.json()

                    for account in resp_json:
                        account_type = account.get("AccountType")
                        alegeus_account_type = ReimbursementAccountType.query.filter_by(
                            alegeus_account_type=account_type
                        ).first()

                        status_code = account.get("AcctStatusCde")
                        alegeus_status = ReimbursementAccountStatus(status_code)

                        plan_id = account.get("PlanId")
                        alegeus_plan_id = ReimbursementPlan.query.filter_by(
                            alegeus_plan_id=plan_id
                        ).first()

                        new_account = ReimbursementAccount(
                            wallet=wallet,
                            plan=alegeus_plan_id,
                            alegeus_flex_account_key=account.get("FlexAccountKey"),
                            alegeus_account_type=alegeus_account_type,
                            status=alegeus_status,
                        )
                        db.session.add(new_account)
                else:
                    log.warning(
                        f"Wallet ID: {wallet.id} has not been configured in WCA"
                    )
                    wallets_failed += 1
            except Exception as e:
                log.error("Something went wrong", exception=e, wallet_id=wallet.id)
                wallets_failed += 1

        db.session.commit()
        log.info(
            f"Succeeded with {total_wallets - wallets_failed} of {total_wallets} wallets"
        )
