from functools import cached_property
from typing import List, Optional

from authn.models.user import User
from health.models.risk_enums import RiskFlagName
from health.services.health_profile_service import HealthProfileService
from health.services.member_risk_service import MemberRiskService
from health.utils.constants import AggregatedFertilityTreatmentStatus
from models.tracks import TrackName


class MemberHealthCohortsService:
    def __init__(self, user: User):
        self._user = user
        self._risk_service = MemberRiskService(user)
        self._health_profile_service = HealthProfileService(user)

    # Use cached properties when more than one method relies on certain data to ensure it is only pulled from the source once

    @cached_property  # noqa, not an ORM model
    def _active_track_names(self) -> List[str]:
        return [t.name for t in self._user.active_tracks]

    @cached_property  # noqa, not an ORM model
    def _fertility_treatment_status(self) -> Optional[str]:
        return self._health_profile_service.get_fertility_treatment_status()

    @cached_property  # noqa, not an ORM model
    def sex_at_birth(self) -> Optional[str]:
        health_profile_sex_at_birth = self._health_profile_service.get_sex_at_birth()
        if health_profile_sex_at_birth:
            return health_profile_sex_at_birth.lower()
        return None

    def is_targeted_for_cycle_tracking(self) -> bool:
        if TrackName.FERTILITY in self._active_track_names:
            if self.sex_at_birth == "female":
                if self._fertility_treatment_status in (
                    AggregatedFertilityTreatmentStatus.PRECONCEPTION
                    + AggregatedFertilityTreatmentStatus.TTC
                ):
                    return True

        return False

    def is_targeted_for_ovulation_tracking(self) -> bool:
        disallowed_risk_flags = [
            RiskFlagName.FEMALE_FEMALE_COUPLE,
            RiskFlagName.SINGLE_PARENT,
        ]

        if TrackName.FERTILITY in self._active_track_names:
            if self.sex_at_birth == "female":
                if not any(
                    self._risk_service.get_active_risk(risk)
                    for risk in disallowed_risk_flags
                ):
                    if self._fertility_treatment_status in (
                        AggregatedFertilityTreatmentStatus.PRECONCEPTION
                        + AggregatedFertilityTreatmentStatus.TTC
                    ):
                        return True
        return False

    def is_targeted_for_ovulation_medication(self) -> bool:
        requires_one_of_risk_flags = [
            RiskFlagName.POLYCYSTIC_OVARIAN_SYNDROME,
            RiskFlagName.UNEXPLAINED_INFERTILITY,
        ]

        disallowed_risk_flags = [
            RiskFlagName.CONGENITAL_ABNORMALITY_AFFECTING_FERTILITY,
            RiskFlagName.HIV_AIDS,
            RiskFlagName.HIV_AIDS_EXISTING,
            RiskFlagName.KIDNEY_DISEASE,
            RiskFlagName.KIDNEY_DISEASE_EXISTING,
        ]

        if TrackName.FERTILITY in self._active_track_names:
            if self.sex_at_birth == "female":
                if any(
                    self._risk_service.get_active_risk(risk)
                    for risk in requires_one_of_risk_flags
                ):
                    if all(
                        not self._risk_service.get_active_risk(risk)
                        for risk in disallowed_risk_flags
                    ):
                        if self._fertility_treatment_status in (
                            AggregatedFertilityTreatmentStatus.TTC
                            + ["considering_fertility_treatment"]
                        ):
                            return True

        return False
