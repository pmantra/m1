from datetime import date
from typing import Any, Dict, List, Optional

from health.models.health_profile import HealthProfile
from health.models.risk_enums import RiskFlagName, RiskInputKey
from health.services.member_risk_service import MemberRiskService
from models.tracks.track import TrackName
from storage.connection import db


# Centralize the place from which Calculators will fetch inputs
# Give preference to provided input value(if it exists)
# Or query from the source if value is not provided
class RiskInputRepository:
    def __init__(
        self,
        member_risk_service: MemberRiskService,
        updated_values: Dict[RiskInputKey, Any],
        health_profile: Optional[HealthProfile] = None,
        active_track_names: Optional[List[str]] = None,
    ):
        self.member_risk_service = member_risk_service
        self.updated_values = updated_values
        self._health_profile = health_profile
        self._active_track_names = active_track_names

    def health_profile(self) -> HealthProfile:
        if self._health_profile is None:
            self._health_profile = (
                db.session.query(HealthProfile)
                .filter(HealthProfile.user_id == self.member_risk_service.user_id)
                .one()
            )
        return self._health_profile

    def age(self) -> Optional[int]:
        value = self.updated_values.get(RiskInputKey.AGE)
        if value is None:
            value = self.health_profile().age
        return value

    def due_date(self) -> Optional[date]:
        value = self.updated_values.get(RiskInputKey.DUE_DATE)
        if value is None:
            value = self.health_profile().due_date
        return value

    def height(self) -> Optional[float]:
        value = self.updated_values.get(RiskInputKey.HEIGHT_IN)
        if value is None:
            value = self.health_profile().height
        return value

    def weight(self) -> Optional[float]:
        value = self.updated_values.get(RiskInputKey.WEIGHT_LB)
        if value is None:
            value = self.health_profile().weight
        return value

    def racial_identity(self) -> Optional[str]:
        value = self.updated_values.get(RiskInputKey.RACIAL_IDENTITY)
        if value is None:
            value = self.health_profile().racial_identity
        return value

    def has_track(self, name: TrackName) -> bool:
        if self._active_track_names is None:
            self._active_track_names = self.member_risk_service._active_track_names()
        return name in self._active_track_names

    def has_risk(self, name: RiskFlagName) -> bool:
        return self.member_risk_service.has_risk(name)

    def has_any_risk(self, names: List[RiskFlagName]) -> bool:
        for name in names:
            if self.has_risk(name):
                return True
        return False
