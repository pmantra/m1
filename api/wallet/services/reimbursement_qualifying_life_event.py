from datetime import datetime
from typing import List, Optional

from wallet.alegeus_api import AlegeusApi, is_request_successful
from wallet.models.reimbursement import ReimbursementAccount, ReimbursementPlan
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory


def apply_qle_to_plan(
    plan: ReimbursementPlan, amount: float, effective_date: datetime
) -> Optional[List[FlashMessage]]:
    api = AlegeusApi()
    messages = []
    for org_settings_assoc in plan.category.allowed_reimbursement_organizations:
        org_settings = org_settings_assoc.reimbursement_organization_settings
        wallets = org_settings.reimbursement_wallets
        for wallet in wallets:
            account = ReimbursementAccount.query.filter_by(
                wallet=wallet, plan=plan
            ).scalar()
            if account and account.alegeus_flex_account_key:
                response = api.post_add_qle(wallet, plan, amount, effective_date)
                if not is_request_successful(response):
                    messages.append(
                        FlashMessage(
                            message=f"Unable to add QLE 😢 for {wallet}",
                            category=FlashMessageCategory.ERROR,
                        )
                    )
                    messages.append(
                        FlashMessage(
                            message=response.json(),
                            category=FlashMessageCategory.WARNING,
                        )
                    )
                else:
                    messages.append(
                        FlashMessage(
                            message=f"Successfully added QLE for {wallet}! 🎉",
                            category=FlashMessageCategory.SUCCESS,
                        )
                    )
    return messages
