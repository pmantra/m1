from __future__ import annotations

from typing import Optional

from authn.models.user import User
from storage.connection import db
from wallet.models.constants import WalletState
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_dashboard import (
    ReimbursementWalletDashboard,
    ReimbursementWalletDashboardCard,
    ReimbursementWalletDashboardCards,
    ReimbursementWalletDashboardType,
)
from wallet.services.reimbursement_wallet import ReimbursementWalletService
from wallet.utils import eligible_wallets as eligible_wallets_utils
from wallet.utils.debit_card import user_is_debit_card_eligible

DASHBOARD_CARD_LINK_URL_TEXT = "%BENEFIT_OVERVIEW_RESOURCE_URL%"


def get_cards_for_user(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user: User,
    reimbursement_organization_settings: Optional[ReimbursementOrganizationSettings],
) -> list[ReimbursementWalletDashboardCard]:
    wallet: ReimbursementWallet | None = (
        user.reimbursement_wallets[0] if user.reimbursement_wallets else None
    )

    # no wallet -- check for wallet eligibility before continuing
    if not wallet and (not reimbursement_organization_settings):
        return []

    dashboard_type = None

    if not wallet:
        dashboard_type = ReimbursementWalletDashboardType.NONE
    else:
        if (rwu := wallet.get_rwu_by_user_id(user_id=user.id)) is None:
            return []

        computed_wallet_state: WalletState = (
            ReimbursementWalletService.resolve_eligible_state(
                default_wallet_state=wallet.state, wallet_user_status=rwu.status
            )
        )

        if computed_wallet_state == WalletState.PENDING:
            dashboard_type = ReimbursementWalletDashboardType.PENDING
        elif computed_wallet_state == WalletState.DISQUALIFIED:
            dashboard_type = ReimbursementWalletDashboardType.DISQUALIFIED

    if not dashboard_type:
        return []

    query = (
        db.session.query(ReimbursementWalletDashboardCard)
        .join(ReimbursementWalletDashboardCards)
        .join(ReimbursementWalletDashboard)
        .filter(ReimbursementWalletDashboard.type == dashboard_type)
        .order_by(ReimbursementWalletDashboardCards.order.asc())
    )

    debit_eligible = (
        wallet.debit_card_eligible
        if wallet
        else user_is_debit_card_eligible(
            user,
            reimbursement_organization_settings,  # type: ignore[arg-type] # Argument 2 to "user_is_debit_card_eligible" has incompatible type "Optional[ReimbursementOrganizationSettings]"; expected "ReimbursementOrganizationSettings"
        )
    )

    if not debit_eligible:
        query = query.filter(
            ReimbursementWalletDashboardCard.require_debit_eligible == False
        )

    return query.all()


def update_wallet_program_overview_url(
    cards: list[ReimbursementWalletDashboardCards],
    reimbursement_settings: Optional[ReimbursementOrganizationSettings],
) -> list[ReimbursementWalletDashboardCards]:
    """
    Updates the Card that contains the link url for the benefit overview resource because it is
    unique to each organization.  If no resource is found, set the link to None.
    """
    for card in cards:
        if card.link_url == DASHBOARD_CARD_LINK_URL_TEXT:
            card.link_url = None
            if (
                reimbursement_settings
                and reimbursement_settings.benefit_overview_resource
            ):
                benefit_overview_url = (
                    reimbursement_settings.benefit_overview_resource.custom_url
                )
                card.link_url = benefit_overview_url
    return cards


def get_dashboard_cards(user: User) -> list[ReimbursementWalletDashboardCards]:
    reimbursement_settings = get_reimbursement_organization_settings(user)
    cards = get_cards_for_user(user, reimbursement_settings)
    updated_cards = update_wallet_program_overview_url(cards, reimbursement_settings)
    return updated_cards


def get_reimbursement_organization_settings(
    user: User,
) -> Optional[ReimbursementOrganizationSettings]:
    eligible_wallet_org_settings = (
        eligible_wallets_utils.get_eligible_wallet_org_settings(
            user_id=user.id,
            filter_out_existing_wallets=False,
        )
    )

    if len(eligible_wallet_org_settings) < 1:
        return None
    return eligible_wallet_org_settings[0]
