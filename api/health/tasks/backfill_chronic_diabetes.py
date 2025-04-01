from authn.models.user import User
from common.health_profile.health_profile_service_client import (
    HealthProfileServiceClient,
)
from common.health_profile.health_profile_service_models import ConditionType
from health.data_models.member_risk_flag import MemberRiskFlag
from health.data_models.risk_flag import RiskFlag
from health.models.risk_enums import RiskFlagName
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_chronic_diabetes() -> None:
    """
    For members that have active risk flag "Diabetes - Existing condition",
    this job creates chronic diabetes condition in health profile service.
    """

    log.info("Backfill chronic diabetes - start")
    num_users_backfill_success: int = 0
    num_users_backfill_failure: int = 0

    users_in_chronic_diabetes_risk = (
        db.session.query(User)
        .join(MemberRiskFlag, MemberRiskFlag.user_id == User.id)
        .join(RiskFlag, RiskFlag.id == MemberRiskFlag.risk_flag_id)
        .filter(RiskFlag.name == RiskFlagName.DIABETES_EXISTING)
        .all()
    )
    log.info(
        f"Retrieved {len(users_in_chronic_diabetes_risk)} members with chronic diabetes risk"
    )

    for user in users_in_chronic_diabetes_risk:
        chronic_diabetes_risk_flags: list[MemberRiskFlag] = (
            db.session.query(MemberRiskFlag)
            .join(RiskFlag, RiskFlag.id == MemberRiskFlag.risk_flag_id)
            .filter(
                MemberRiskFlag.user_id == user.id,
                RiskFlag.name == RiskFlagName.DIABETES_EXISTING,
            )
            .all()
        )
        has_active_chronic_diabetes_risk = any(
            chronic_diabetes_risk_flag.is_active()
            for chronic_diabetes_risk_flag in chronic_diabetes_risk_flags
        )
        if not has_active_chronic_diabetes_risk:
            log.info(f"User {user.id}'s chronic diabetes risk is not active - skipping")
            continue

        try:
            health_profile_service_client = HealthProfileServiceClient(user=user)
            member_conditions = [
                {
                    "condition_type": ConditionType.CHRONIC_DIABETES.value,
                    "status": "active",
                    "onset_date": None,
                    "modifier": {
                        "id": user.id,
                        "name": user.full_name,
                        "role": "member",
                        "verticals": [],
                    },
                }
            ]
            health_profile_service_client.put_member_conditions(
                member_conditions=member_conditions
            )
            num_users_backfill_success += 1
            log.info(f"Successfully back-filled chronic diabetes for user {user.id}")
        except Exception as e:
            num_users_backfill_failure += 1
            log.error(
                f"Failed to backfill chronic diabetes for user {user.id}",
                error=str(e),
            )

    log.info(f"Successful backfill {num_users_backfill_success}")
    log.info(f"Failed backfill {num_users_backfill_failure}")
    log.info("Backfill chronic diabetes - finish")
