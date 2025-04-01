from __future__ import annotations

import datetime
from typing import List, Optional

from sqlalchemy import and_
from sqlalchemy.orm.exc import MultipleResultsFound

from eligibility import service as e9y_service
from eligibility.e9y import model as e9y_model
from models.base import db
from models.enterprise import Organization
from models.tracks import ClientTrack, MemberTrack
from tracks import service as tracks_service
from utils.log import logger
from wallet.models.constants import WalletState, WalletUserStatus
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.utils.common import get_verification_record_data, has_tenure_exceeded

log = logger(__name__)


def get_eligible_wallet_org_settings(
    user_id: int,
    e9y_svc: e9y_service.EnterpriseVerificationService | None = None,
    organization_id: Optional[int] = None,
    filter_out_existing_wallets: bool = True,
) -> List[ReimbursementOrganizationSettings]:
    """
    eligible wallets:
        org settings active,
        user employed by org,
        wallet not activated yet,

    matches the user's track if there's a required track
    """
    e9y_svc = e9y_svc or e9y_service.EnterpriseVerificationService()
    if not organization_id:
        track_svc = tracks_service.TrackSelectionService()
        if not track_svc.is_enterprise(user_id=user_id):
            return []

        organization_id = track_svc.get_organization_id_for_user(user_id=user_id)

    now = datetime.datetime.now()
    settings_query = (
        # TODO: [multitrack] Ensure this works when a user has multiple tracks.
        db.session.query(ReimbursementOrganizationSettings, MemberTrack)
        .join(
            Organization,
            Organization.id == ReimbursementOrganizationSettings.organization_id,
        )
        .join(
            ClientTrack,
            ClientTrack.organization_id == Organization.id,
        )
        .join(MemberTrack, MemberTrack.client_track_id == ClientTrack.id)
    )
    if filter_out_existing_wallets:
        settings_query = settings_query.outerjoin(
            ReimbursementWalletUsers,
            ReimbursementWalletUsers.user_id == MemberTrack.user_id,
        ).outerjoin(
            ReimbursementWallet,
            and_(
                ReimbursementWallet.id
                == ReimbursementWalletUsers.reimbursement_wallet_id,
                ReimbursementWallet.reimbursement_organization_settings_id
                == ReimbursementOrganizationSettings.id,
            ),
        )

    settings_query = settings_query.filter(
        ReimbursementOrganizationSettings.started_at < now,
        MemberTrack.user_id == user_id,
        MemberTrack.active == True,
        Organization.id == organization_id,
    )
    if filter_out_existing_wallets:
        settings_query = settings_query.filter(ReimbursementWallet.id.is_(None))

    settings = settings_query.all()

    _sub_population_eligible_reimbursement_organization_settings: dict = {}

    def _is_eligible_reimbursement_organization_settings(
        reimbursement_organization_settings_id: int,
        sub_population_id: int,
    ) -> bool:
        """
        An internal helper function to determine if a ReimbursementOrganizationSetting
        is eligible for the specified sub-population. If the information for the
        sub-population is not in the stored dictionary, it will retrieve the information
        from the Eligibility service.
        """
        # If no population was defined, all features are eligible
        if sub_population_id is None:
            return True

        # If the eligible reimbursement organization settings isn't already saved, retrieve it
        if (
            sub_population_id
            not in _sub_population_eligible_reimbursement_organization_settings
        ):
            _sub_population_eligible_reimbursement_organization_settings[
                sub_population_id
            ] = e9y_svc.get_eligible_features_by_sub_population_id(
                sub_population_id=sub_population_id,
                feature_type=e9y_model.FeatureTypes.WALLET_FEATURE,
            )
        # Get the stored eligible reimbursement organization settings for the specified sub-population
        eligible_reimbursement_organization_settings = (
            _sub_population_eligible_reimbursement_organization_settings[
                sub_population_id
            ]
        )
        # Check if the saved settings is None, and if so, all are considered eligible
        if eligible_reimbursement_organization_settings is None:
            return True
        # Check to see if the ID is in the saved settings IDs
        return (
            reimbursement_organization_settings_id
            in eligible_reimbursement_organization_settings
        )

    def _is_tenured_reimbursement_organization_settings(
        setting: ReimbursementOrganizationSettings,
        member_user_id: int,
    ) -> bool:
        """
        An internal helper function to determine if a ReimbursementOrganizationSetting
        is eligible based on required_tenure_days field and user start_date from the e9y verification file.
        """
        # If required tenure days uses default value return
        if setting.required_tenure_days == 0:
            return True

        # Get the members e9y record to determine start_date
        verification = get_verification_record_data(
            user_id=member_user_id,
            organization_id=setting.organization_id,
            eligibility_service=e9y_svc,
        )
        if verification is None:
            log.error("Missing e9y verification record.", user_id=member_user_id)
            return False

        start_date = verification.record.get("employee_start_date")

        if start_date is None:
            log.error(
                "Missing employee_start_date from e9y record.", user_id=member_user_id
            )
            return False

        # determine tenure rule given start_date, required_tenure_days and current day
        return has_tenure_exceeded(start_date, days=setting.required_tenure_days)

    eligibility = [
        setting
        for (setting, member_track) in settings
        if (
            setting.is_active
            and (
                # TODO: use setting.required_track instead of setting.required_module_id
                setting.required_module_id is None
                or setting.required_module.name == member_track.name
            )
            and (
                _is_eligible_reimbursement_organization_settings(
                    reimbursement_organization_settings_id=setting.id,
                    sub_population_id=member_track.sub_population_id,
                )
            )
            and (
                _is_tenured_reimbursement_organization_settings(
                    setting=setting,
                    member_user_id=user_id,
                )
            )
        )
    ]

    log.info(
        "Calculated eligibility.",
        user_id=user_id,
        organization_id=organization_id,
        settings=settings,
        filter_out_existing_wallets=filter_out_existing_wallets,
        eligibility=eligibility,
    )

    return eligibility


def get_user_eligibility_start_date(
    user_id: int, org_id: Optional[int]
) -> Optional[datetime.date]:
    """
    Get the start date for an organization employee.
    This logic was previously part of the TenureCategoryRule.
    """
    if not org_id:
        return None
    eligibility_service = e9y_service.get_verification_service()
    verification = get_verification_record_data(
        user_id=user_id,
        organization_id=org_id,
        eligibility_service=eligibility_service,
    )
    if not verification:
        return None
    start_date: str = verification.record.get("employee_start_date")

    if start_date is None:
        start_date = verification.record.get("created_at")

    if not start_date:
        log.info(
            "Eligibility verification record missing start_date.",
            user_id=user_id,
            organization_id=org_id,
        )
        return None
    formatted_start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
    return formatted_start_date


def qualified_reimbursement_wallet(user_id: int) -> Optional[ReimbursementWallet]:
    """
    Returns a qualified wallet for the user or None if one does not exist.
    """
    try:
        wallet = (
            ReimbursementWallet.query.join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .filter(
                ReimbursementWalletUsers.user_id == user_id,
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
                ReimbursementWallet.state == WalletState.QUALIFIED,
            )
            .one_or_none()
        )
    except MultipleResultsFound:
        log.info(f"Multiple qualified wallets found for user_id: {user_id}")
        return None

    return wallet


def active_reimbursement_wallet(user_id: int) -> Optional[ReimbursementWallet]:
    """
    Returns a wallet in QUALIFIED or RUN_OUT state, None if not found
    """
    try:
        wallet = (
            ReimbursementWallet.query.join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .filter(
                ReimbursementWalletUsers.user_id == user_id,
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
                ReimbursementWallet.state.in_(
                    {WalletState.QUALIFIED, WalletState.RUNOUT}
                ),
            )
            .one_or_none()
        )
    except MultipleResultsFound:
        log.info(f"Multiple active wallets found for user_id: {user_id}")
        return None

    return wallet
