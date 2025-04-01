from __future__ import annotations

from typing import List

from maven import feature_flags

from authn.models.user import User
from models.enterprise import InboundPhoneNumber
from utils.launchdarkly import user_context
from utils.log import logger
from wallet.models.models import MemberWalletSummary
from wallet.services.reimbursement_wallet import ReimbursementWalletService

log = logger(__name__)

PHONE_NUMBER_RELEASE_FLAG = "include-inbound-phone-number"


def should_include_inbound_phone_number(user: User | None) -> bool:
    """
    Returns True if we should include inbound phone number in the wallet message sla
    """
    if not user:
        log.warn("Could not determine feature flag, missing user.")
        return False

    return feature_flags.bool_variation(
        PHONE_NUMBER_RELEASE_FLAG,
        context=user_context(user),
        default=False,
    )


def get_inbound_phone_number(user: User | None) -> str | None:
    """
    # Returns inbound phone number for a user's organization
    """
    # Return phone number if ff ON and wallet enabled for this user
    if user is None:
        return None
    if user.organization_v2 is None:
        log.error(
            "Missing member organization when trying to get inbound phone number",
            user_id=user.id,
        )
        return None
    # Get all enrolled wallets
    member_wallets: List[
        MemberWalletSummary
    ] = ReimbursementWalletService().wallet_repo.get_wallet_summaries(user_id=user.id)
    enrolled_wallets: List[
        MemberWalletSummary
    ] = ReimbursementWalletService.get_enrolled_wallets(
        wallets=member_wallets
    )  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Union[List[MemberWalletSummary], List[ClinicPortalMemberWalletSummary]]", variable has type "List[MemberWalletSummary]")
    wallet_enabled = len(enrolled_wallets) > 0
    if should_include_inbound_phone_number(user) and wallet_enabled:
        inbound_number = InboundPhoneNumber.query.filter(
            InboundPhoneNumber.organizations.contains(user.organization_v2)
        ).one_or_none()
        if inbound_number:
            return inbound_number.number
    return None
