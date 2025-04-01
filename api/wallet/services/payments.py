from typing import Mapping

from redset.exceptions import LockTimeout

from audit_log.utils import emit_audit_log_update
from authn.models.user import User
from common import payments_gateway
from direct_payment.billing.constants import INTERNAL_TRUST_PAYMENT_GATEWAY_URL
from storage.connection import db
from tasks.queues import job
from utils.cache import RedisLock
from utils.log import logger
from wallet.models.constants import BillingConsentAction
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_billing import ReimbursementWalletBillingConsent

log = logger(__name__)


def assign_payments_customer_id_to_wallet(
    wallet: ReimbursementWallet, headers: Mapping[str, str] = None  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
) -> bool:
    # To avoid creating duplicate records, especially because this method calls
    # external resources, only proceed if a lock is available. This is
    # particularly for cases where multiple jobs have been queued.

    log.warning(
        "Assigning Payments Customer ID to Wallet",
        reimbursement_wallet_id=str(wallet.id),
    )
    try:
        with RedisLock(
            f"assign_payments_customer_id_to_wallet__{wallet.id}", timeout=0, expires=60
        ):
            if wallet.payments_customer_id:
                raise ValueError("Wallet already has a Payments Customer ID")

            try:
                metadata = {"reimbursement_wallet_id": wallet.id}
                if (
                    hasattr(wallet, "reimbursement_wallet_benefit")
                    and wallet.reimbursement_wallet_benefit
                ):
                    metadata[
                        "maven_benefit_id"
                    ] = wallet.reimbursement_wallet_benefit.maven_benefit_id
                else:
                    log.warning(
                        "Wallet has no benefit id",
                        reimbursement_wallet_id=str(wallet.id),
                    )
                client = payments_gateway.get_client(INTERNAL_TRUST_PAYMENT_GATEWAY_URL)  # type: ignore[arg-type] # Argument 1 to "get_client" has incompatible type "Optional[str]"; expected "str"
                first_name, last_name, _ = wallet.get_first_name_last_name_and_dob()
                payments_customer = client.create_customer(
                    name=f"{first_name} {last_name}", metadata=metadata, headers=headers
                )
            except payments_gateway.PaymentsGatewayException as e:
                log.error(
                    "Failed to generate payments customer", wallet=wallet, error=e
                )
            else:
                # Would be nice to have a check that the current value is null without resorting to
                # SQLAlchemy primitives. The lock should make this a non-issue though.
                wallet.payments_customer_id = payments_customer.customer_id
                db.session.add(wallet)
                return True
    except LockTimeout as e:
        log.info("Failed to acquire lock", wallet=wallet, error=e)

    return False


@job
def assign_payments_customer_id_to_wallet_async(wallet_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    wallet = ReimbursementWallet.query.filter(
        ReimbursementWallet.id == wallet_id
    ).one_or_none()

    if wallet:
        assign_payments_customer_id_to_wallet(wallet)
        db.session.commit()
    else:
        log.warning(
            "assign_payments_customer_id_to_wallet_async failed: missing wallet",
            wallet_id=wallet_id,
        )


def assign_payments_customer_id_to_org(
    org_settings: ReimbursementOrganizationSettings, headers: Mapping[str, str] = None  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
) -> None:
    # To avoid creating duplicate records, especially because this method calls
    # external resources, only proceed if a lock is available.

    try:
        with RedisLock(
            f"assign_payments_customer_id_to_org__{org_settings.id}",
            timeout=0,
            expires=60,
        ):
            if org_settings.payments_customer_id:
                raise ValueError(
                    "Organization Settings already has a Payments Customer ID"
                )

            try:
                metadata = {
                    "organization_id": org_settings.organization_id,
                    "reimbursement_organization_settings_id": org_settings.id,
                }
                # remove once auth in admin work is completed
                client = payments_gateway.get_client(INTERNAL_TRUST_PAYMENT_GATEWAY_URL)  # type: ignore[arg-type] # Argument 1 to "get_client" has incompatible type "Optional[str]"; expected "str"
                payments_customer = client.create_customer(
                    name=f"{org_settings.organization.name}",  # update for multi-population
                    metadata=metadata,
                    headers=headers,
                )
            except payments_gateway.PaymentsGatewayException as e:
                log.error(
                    "Failed to generate payments customer",
                    org_settings=org_settings,
                    error=e,
                )
                raise RuntimeError(f"Failed to create payments customer. Error: {e}")
            else:
                # Would be nice to have a check that the current value is null without resorting to
                # SQLAlchemy primitives. The lock should make this a non-issue though.
                org_settings.payments_customer_id = payments_customer.customer_id
                db.session.add(org_settings)
                db.session.commit()
    except LockTimeout as e:
        log.info("Failed to acquire lock", org_settings=org_settings, error=e)
        raise RuntimeError("Failed to acquire lock for organization customer")


def save_employer_direct_billing_account(
    org_settings: ReimbursementOrganizationSettings,
    account_type: str,
    account_holder_type: str,
    account_number: str,
    routing_number: str,
    headers: Mapping[str, str] = None,  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
) -> None:
    # To avoid creating duplicate records, especially because this method calls
    # external resources, only proceed if a lock is available.

    try:
        with RedisLock(
            f"save_employer_direct_billing_account__{org_settings.id}",
            timeout=0,
            expires=60,
        ):
            if not org_settings.payments_customer_id:
                try:
                    assign_payments_customer_id_to_org(org_settings, headers)
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to save direct billing account. Error: {e}"
                    )

            try:
                # remove once auth in admin work is completed
                client = payments_gateway.get_client(INTERNAL_TRUST_PAYMENT_GATEWAY_URL)  # type: ignore[arg-type] # Argument 1 to "get_client" has incompatible type "Optional[str]"; expected "str"
                client.add_bank_account(
                    customer_id=org_settings.payments_customer_id,  # type: ignore[arg-type] # Argument "customer_id" to "add_bank_account" of "PaymentsGatewayClient" has incompatible type "Optional[str]"; expected "str"
                    name=org_settings.organization.name,
                    account_type=account_type,
                    account_holder_type=account_holder_type,
                    account_number=account_number,
                    routing_number=routing_number,
                    headers=headers,
                )
                emit_audit_log_update(org_settings)
            except payments_gateway.PaymentsGatewayException as e:
                log.error(
                    "Failed to save direct billing account",
                    org_settings=org_settings,
                    error=e,
                )
                raise RuntimeError(f"Failed to save direct billing account. Error: {e}")

    except LockTimeout as e:
        log.info("Failed to acquire lock", org_settings=org_settings, error=e)
        raise RuntimeError("Failed to acquire lock for billing account")


CURRENT_BILLING_CONSENT_VERSION = 1
"""Version value to save for new Member consents."""

MINIMUM_BILLING_CONSENT_VERSION = CURRENT_BILLING_CONSENT_VERSION
"""
Member must have consented to this version or greater for consent to be active.
May be less than the current version if we need to track a new version but not reset consent.
"""


def get_direct_payments_billing_consent(wallet: ReimbursementWallet) -> bool:
    """
    Returns the current consent state for the wallet.
    """
    consent = (
        ReimbursementWalletBillingConsent.query.filter(
            ReimbursementWalletBillingConsent.reimbursement_wallet_id == wallet.id
        )
        .filter(
            ReimbursementWalletBillingConsent.version >= MINIMUM_BILLING_CONSENT_VERSION
        )
        .order_by(ReimbursementWalletBillingConsent.id.desc())
        .limit(1)
        .one_or_none()
    )

    return consent is not None and consent.action == BillingConsentAction.CONSENT


def set_direct_payments_billing_consent(
    wallet: ReimbursementWallet, actor: User, consent_granted: bool, ip_address: str
) -> bool:
    """
    Save a new consent record for the wallet. Returns the new state.
    """
    consent_action = (
        BillingConsentAction.CONSENT if consent_granted else BillingConsentAction.REVOKE
    )
    consent = ReimbursementWalletBillingConsent(
        reimbursement_wallet_id=wallet.id,
        version=CURRENT_BILLING_CONSENT_VERSION,
        action=consent_action,
        acting_user_id=actor.id,
        ip_address=ip_address,
    )

    db.session.add(consent)
    db.session.commit()

    return consent.action == BillingConsentAction.CONSENT
