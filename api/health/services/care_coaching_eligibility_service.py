from __future__ import annotations

from typing import Optional, Union

from authn.models.user import User

__all__ = ("CareCoachingEligibilityService",)

from health.models.risk_enums import RiskFlagName
from health.services.health_profile_service import HealthProfileService
from models.tracks import TrackName
from models.tracks.client_track import TrackModifiers
from utils.log import logger

log = logger(__name__)

ELIGIBLE_FERTILITY_TREATMENT_STATUSES = {
    "ttc_no_treatment",
    "ttc_no_iui_ivf",
    "considering_fertility_treatment",
    "undergoing_iui",
    "undergoing_ivf",
}

ELIGIBLE_PREGNANCY_RISK_FLAGS = {
    RiskFlagName.GESTATIONAL_DIABETES_AT_RISK,
    RiskFlagName.PREECLAMPSIA_HIGH,
    RiskFlagName.PREECLAMPSIA_MODERATE,
    RiskFlagName.PRETERM_LABOR_AT_RISK,
    RiskFlagName.DIABETES_EXISTING,
    RiskFlagName.GESTATIONAL_DIABETES_CURRENT_PREGNANCY,
    RiskFlagName.HIGH_BLOOD_PRESSURE,
    RiskFlagName.HIGH_BLOOD_PRESSURE_CURRENT_PREGNANCY,
    RiskFlagName.PREECLAMPSIA_CURRENT_PREGNANCY,
    RiskFlagName.ECLAMPSIA_CURRENT_PREGNANCY,
}


class CareCoachingEligibilityService:

    __FERTILITY_STATUS_EMPTY_ARG = (
        object()
    )  # sentinel value since fertility treatment status could be None

    def is_user_eligible_for_care_coaching(
        self,
        user: User,
        fertility_treatment_status: Union[
            Optional[str], object
        ] = __FERTILITY_STATUS_EMPTY_ARG,
    ) -> bool:
        if not user.country_code or user.country_code != "US":
            log.info(
                "Calculated care coaching eligibility",
                user_id=user.id,
                reason="non_us",
                is_eligible_for_care_coaching=False,
            )
            return False

        active_track_names = [t.name for t in user.active_tracks]

        if TrackName.FERTILITY in active_track_names:
            if fertility_treatment_status == self.__FERTILITY_STATUS_EMPTY_ARG:
                health_profile_service = HealthProfileService(user)
                fertility_treatment_status = (
                    health_profile_service.get_fertility_treatment_status()
                )
            is_eligible = (
                fertility_treatment_status in ELIGIBLE_FERTILITY_TREATMENT_STATUSES
            )

            if is_eligible:
                log.info(
                    "Calculated care coaching eligibility",
                    user_id=user.id,
                    reason="fertility_status",
                    is_eligible_for_care_coaching=True,
                )
            else:
                log.info(
                    "Calculated care coaching eligibility",
                    user_id=user.id,
                    reason="fertility_status",
                    is_eligible_for_care_coaching=False,
                )

            return is_eligible
        elif TrackName.PREGNANCY in active_track_names:
            pregnancy_track_is_doula_only = any(
                t.name == TrackName.PREGNANCY
                and TrackModifiers.DOULA_ONLY in t.track_modifiers
                for t in user.active_tracks
            )

            if pregnancy_track_is_doula_only:
                log.info(
                    "Calculated care coaching eligibility",
                    user_id=user.id,
                    reason="pregnancy_is_doula_only",
                    is_eligible_for_care_coaching=False,
                )
                return False

            current_risk_flag_names = [
                risk_flag.name for risk_flag in user.current_risk_flags()
            ]

            # If the user has the LATE_THIRD_TRIMESTER risk flag, they are ineligible
            if RiskFlagName.LATE_THIRD_TRIMESTER in current_risk_flag_names:
                log.info(
                    "Calculated care coaching eligibility",
                    user_id=user.id,
                    reason="late_third_trimester",
                    is_eligible_for_care_coaching=False,
                )
                return False

            is_eligible = any(
                risk_flag in current_risk_flag_names
                for risk_flag in ELIGIBLE_PREGNANCY_RISK_FLAGS
            )

            if is_eligible:
                log.info(
                    "Calculated care coaching eligibility",
                    user_id=user.id,
                    reason="pregnancy_risk_flags",
                    is_eligible_for_care_coaching=True,
                )
            else:
                log.info(
                    "Calculated care coaching eligibility",
                    user_id=user.id,
                    reason="pregnancy_risk_flags",
                    is_eligible_for_care_coaching=False,
                )

            return is_eligible

        log.info(
            "Calculated care coaching eligibility",
            user_id=user.id,
            reason="no_eligible_active_track",
            is_eligible_for_care_coaching=False,
        )
        return False
