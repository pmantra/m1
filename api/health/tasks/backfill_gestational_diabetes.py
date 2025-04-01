import datetime

from authn.models.user import User
from common.health_profile.health_profile_service_client import (
    HealthProfileServiceClient,
)
from common.health_profile.health_profile_service_models import (
    GestationalDiabetesStatus,
)
from health.data_models.member_risk_flag import MemberRiskFlag
from health.data_models.risk_flag import RiskFlag
from health.models.risk_enums import RiskFlagName
from models.tracks import TrackName
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_gestational_diabetes() -> None:
    """
    For members that
        - are currently in the pregnancy track
        - have risk flag "Gestational diabetes - Current pregnancy" added in the last 40 weeks
    this job creates gestational diabetes condition linked to the current pregnancy in health profile service.
    """

    log.info("Backfill gestational diabetes - start")
    num_users_backfill_success: int = 0
    num_users_backfill_failure: int = 0

    # Step 1: get users that have "Gestational diabetes - Current pregnancy" added in the last 40 weeks
    current_timestamp = datetime.datetime.now(datetime.timezone.utc)
    cutoff_timestamp = current_timestamp - datetime.timedelta(weeks=40)
    users_in_gdm_risk = (
        db.session.query(User)
        .join(MemberRiskFlag, MemberRiskFlag.user_id == User.id)
        .join(RiskFlag, RiskFlag.id == MemberRiskFlag.risk_flag_id)
        .filter(
            RiskFlag.name == RiskFlagName.GESTATIONAL_DIABETES_CURRENT_PREGNANCY,
            MemberRiskFlag.created_at is not None,
            MemberRiskFlag.created_at >= cutoff_timestamp,
        )
        .all()
    )

    # Step 2: filter out users not in the pregnancy track
    pregnant_users_in_gdm_risk = [
        user
        for user in users_in_gdm_risk
        if any(track.name == TrackName.PREGNANCY for track in user.active_tracks)
    ]
    log.info(f"Retrieved {len(pregnant_users_in_gdm_risk)} pregnant users in gdm risk")

    # Step 3: send GDM update to health profile service if the GDM risk is active
    for user in pregnant_users_in_gdm_risk:
        gdm_risk_flags: list[MemberRiskFlag] = (
            db.session.query(MemberRiskFlag)
            .join(RiskFlag, RiskFlag.id == MemberRiskFlag.risk_flag_id)
            .filter(
                MemberRiskFlag.user_id == user.id,
                RiskFlag.name == RiskFlagName.GESTATIONAL_DIABETES_CURRENT_PREGNANCY,
            )
            .all()
        )
        has_active_gdm_risk = any(
            gdm_risk_flag.is_active() for gdm_risk_flag in gdm_risk_flags
        )
        if not has_active_gdm_risk:
            log.info(f"User {user.id}'s GDM risk is not active - skipping")
            continue

        try:
            health_profile_service_client = HealthProfileServiceClient(user=user)
            health_profile_service_client.put_current_pregnancy_and_gdm_status(
                pregnancy_due_date=user.health_profile.due_date,
                gdm_status=GestationalDiabetesStatus.HAS_GDM,
                gdm_onset_date=None,
            )
            num_users_backfill_success += 1
            log.info(
                f"Successfully back-filled gestational diabetes for user {user.id}"
            )
        except Exception as e:
            num_users_backfill_failure += 1
            log.error(
                f"Failed to backfill gestational diabetes for user {user.id}",
                error=str(e),
            )

    log.info(f"Successful backfill {num_users_backfill_success}")
    log.info(f"Failed backfill {num_users_backfill_failure}")
    log.info("Backfill gestational diabetes - finish")
