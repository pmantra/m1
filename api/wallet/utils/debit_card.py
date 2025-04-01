from authn.models.user import User
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)


def user_is_debit_card_eligible(
    user: User, reimbursement_organization_settings: ReimbursementOrganizationSettings
) -> bool:
    # @todo switch to user.country_code once cut-over to new profile logic is done
    # We're also removing the logic to check user.country due to it being unreliable at the moment.
    # We will validate country in the request form
    return reimbursement_organization_settings.debit_card_enabled
