from typing import List, Optional

from maven import observability

from authn.models.user import User
from models.enterprise import Organization
from models.profiles import MemberProfile
from models.tracks import TrackName
from storage.connection import db
from tracks import service as tracks_service
from utils.log import logger
from wallet.models.constants import (
    FERTILITY_EXPENSE_TYPES,
    MemberType,
    WalletState,
    WalletUserStatus,
)
from wallet.models.models import MemberTypeDetails, MemberTypeDetailsFlags
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_benefit import ReimbursementWalletBenefit
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.utils.eligible_wallets import (
    active_reimbursement_wallet,
    get_eligible_wallet_org_settings,
)
from wallet.utils.wallet_benefit_id import generate_wallet_benefit

log = logger(__name__)


def assign_benefit_id(wallet: ReimbursementWallet) -> ReimbursementWalletBenefit:  # type: ignore[return] # Missing return statement
    if wallet.reimbursement_wallet_benefit:
        raise ValueError("Wallet already has a Benefit ID")

    try:
        wallet_benefit = generate_wallet_benefit()

        # Assign this by column + value and not by relationship + object or SQLAlchemy will set any existing
        # benefit for this wallet to null wallet id instead of causing a duplicate key error.
        wallet_benefit.reimbursement_wallet_id = wallet.id
        db.session.add(wallet_benefit)

        return wallet_benefit
    except Exception as e:
        log.exception(
            "Failed to assign Benefit ID",
            reimbursement_wallet_id=str(wallet.id),
            error=str(e),
        )


def get_member_type(user: User) -> MemberType:
    details = get_member_type_details(user)
    return details.member_type


def get_member_type_details(user: User) -> MemberTypeDetails:
    # Fetches wallet in QUALIFIED or RUN_OUT state
    active_wallet = active_reimbursement_wallet(user.id)

    if active_wallet:
        details = get_member_type_details_from_wallet(active_wallet)
    else:
        details = get_member_type_details_from_user(user)

    # Not used to flag Gold but used to determine eligibility
    for track in user.active_tracks:
        if track.name in [TrackName.FERTILITY, TrackName.EGG_FREEZING]:
            details.flags.member_track = True
            break

    return details


def get_member_type_details_from_wallet(
    wallet: ReimbursementWallet,
) -> MemberTypeDetails:
    """
    Return the MemberType Details based on the passed wallet.
    """
    member_type = MemberType.MAVEN_GREEN

    flags = MemberTypeDetailsFlags(
        wallet_organization=True,
        wallet_active=wallet.state in {WalletState.QUALIFIED, WalletState.RUNOUT},
    )

    if wallet.reimbursement_organization_settings.direct_payment_enabled:
        flags.direct_payment = True

    if wallet.primary_expense_type in FERTILITY_EXPENSE_TYPES:
        flags.wallet_expense_type = True

    for active_wallet_user in wallet.all_active_users:
        if (
            active_wallet_user.member_profile
            and active_wallet_user.member_profile.country_code == "US"
        ):
            flags.member_country = True
            break

    if (
        flags.wallet_active
        and flags.direct_payment
        and flags.member_country
        and flags.wallet_expense_type
    ):
        member_type = MemberType.MAVEN_GOLD

    details = MemberTypeDetails(
        member_type=member_type, flags=flags, active_wallet=wallet
    )
    return details


def get_member_type_details_from_user(user: User) -> MemberTypeDetails:
    """
    Return the MemberTypeDetails based solely on the passed User.
    Does not use the user's Wallet. See get_member_type_details.
    """
    flags = MemberTypeDetailsFlags()

    track_svc = tracks_service.TrackSelectionService()
    if track_svc.is_enterprise(user_id=user.id):
        member_type = MemberType.MAVEN_ACCESS

        eligible_wallet_org_settings = get_eligible_wallet_org_settings(
            user_id=user.id,
            filter_out_existing_wallets=False,
        )

        if len(eligible_wallet_org_settings) > 0:
            ros = eligible_wallet_org_settings[0]
            flags.wallet_organization = True

            if ros.direct_payment_enabled:
                flags.direct_payment = True
    else:
        member_type = MemberType.MARKETPLACE

    if user.member_profile and user.member_profile.country_code == "US":
        flags.member_country = True

    details = MemberTypeDetails(
        member_type=member_type, flags=flags, active_wallet=None
    )
    return details


@observability.wrap
def find_maven_gold_wallet_user_objs(filters: Optional[List] = None) -> List:
    # WARNING: Do not update this logic without updating the global Green/Gold determination.
    query = (
        db.session.query(
            Organization,
            ReimbursementOrganizationSettings,
            ReimbursementWallet,
            ReimbursementWalletUsers,
            MemberProfile,
        )
        .join(
            ReimbursementOrganizationSettings,
            Organization.id == ReimbursementOrganizationSettings.organization_id,
        )
        .join(
            ReimbursementWallet,
            ReimbursementWallet.reimbursement_organization_settings_id
            == ReimbursementOrganizationSettings.id,
        )
        .join(
            ReimbursementWalletUsers,
            ReimbursementWalletUsers.reimbursement_wallet_id == ReimbursementWallet.id,
        )
        .join(MemberProfile, MemberProfile.user_id == ReimbursementWalletUsers.user_id)
        .filter(ReimbursementOrganizationSettings.direct_payment_enabled == True)
        .filter(
            ReimbursementWallet.state.in_({WalletState.QUALIFIED, WalletState.RUNOUT})
        )
        .filter(
            ReimbursementWallet.primary_expense_type.in_(
                [e.value for e in FERTILITY_EXPENSE_TYPES]
            )
        )
        .filter(ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE)
        .filter(MemberProfile.country_code == "US")
    )

    if filters:
        for filter_ in filters:
            query = query.filter(filter_)
    query = query.order_by(ReimbursementWallet.id.desc())
    query_results = query.all()
    return query_results
