from datetime import date
from typing import List

from authn.models.user import User
from health.data_models.member_risk_flag import MemberRiskFlag
from health.services.member_risk_service import MemberRiskService
from health.services.risk_service import RiskService


# view Model for member_profile_edit_risk_flags.html
class MemberRisksAdminModel:
    def __init__(self, user: User):
        self.user = user
        self.service = MemberRiskService(self.user)
        self._all = self.service.get_member_risks(False, False)
        self.allow_edit = True
        self.user_id = user.id

        self._all = sorted(
            self._all,
            key=lambda x: (
                not x.is_active(),  # sort active first
                x.risk_flag.name,
                x.start if x.start else date.min,
                x.end if x.end else date.min,
            ),
        )
        self._risk_names = RiskService().get_all_names()

    def all(self) -> List[MemberRiskFlag]:
        return self._all

    def any(self) -> bool:
        return len(self._all) > 0

    def risk_names(self) -> List[str]:
        return self._risk_names
