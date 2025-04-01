from flask import request

from common.services.api import PermissionedUserResource
from direct_payment.consent.schemas.billing_consent import WalletBillingConsentSchema
from wallet.resources.common import WalletResourceMixin
from wallet.services.payments import (
    get_direct_payments_billing_consent,
    set_direct_payments_billing_consent,
)


class BillingConsentResource(PermissionedUserResource, WalletResourceMixin):
    def get(self, wallet_id: int) -> dict:
        wallet = self._wallet_or_404(self.user, wallet_id)

        consent_granted = get_direct_payments_billing_consent(wallet)
        response = {"consent_granted": consent_granted}

        response_schema = WalletBillingConsentSchema()
        return response_schema.dump(response)

    def post(self, wallet_id: int) -> dict:
        wallet = self._wallet_or_404(self.user, wallet_id)

        ip_address = request.headers.get("X-Real-IP", type=str)
        consent_granted = set_direct_payments_billing_consent(
            wallet=wallet, actor=self.user, consent_granted=True, ip_address=ip_address  # type: ignore[arg-type] # Argument "ip_address" to "set_direct_payments_billing_consent" has incompatible type "Optional[str]"; expected "str"
        )
        response = {"consent_granted": consent_granted}

        response_schema = WalletBillingConsentSchema()
        return response_schema.dump(response)
