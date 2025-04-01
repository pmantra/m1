from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy import delete

from authn.models.user import User
from health.data_models.member_risk_flag import MemberRiskFlag
from health.models.health_profile import HealthProfile
from health.services.member_risk_service import MemberRiskService


class RiskTestUtils:
    @staticmethod
    def set_age(session, user: User, age: int) -> None:
        today = date.today()
        health_profile: HealthProfile = user.health_profile
        health_profile.json["birthday"] = date(today.year - age, 1, 1).isoformat()
        session.add(health_profile)
        session.commit()

    @staticmethod
    def set_height_weight(
        session, user: User, height: int, weight: int, commit: bool = True
    ) -> None:
        health_profile: HealthProfile = user.health_profile
        health_profile.json["height"] = height
        health_profile.json["weight"] = weight
        session.add(health_profile)
        if commit:
            session.commit()

    @staticmethod
    def delete_member_risks(session, user: User) -> None:
        session.execute(delete(MemberRiskFlag).where(MemberRiskFlag.user_id == user.id))
        session.commit()
        assert RiskTestUtils.get_risks(user, False) == []

    @staticmethod
    def add_member_risk(
        user: User,
        name: str,
        value: Optional[int] = None,
        created_at_offset: Optional[int] = None,
    ) -> None:
        mrs = MemberRiskService(user)
        res = mrs.set_risk(name, value)
        mr = res.created_risk
        if created_at_offset is not None and mr is not None:
            mr.created_at = datetime.today() - timedelta(days=created_at_offset)

    @staticmethod
    def delete_member_risk(user: User, name: str) -> None:
        mrs = MemberRiskService(user)
        mrs.clear_risk(name)

    @staticmethod
    def get_risks(user: User, active: bool = True) -> List[MemberRiskFlag]:
        mrs = MemberRiskService(user)
        return mrs.get_member_risks(active, False)

    @staticmethod
    def get_risk_names(user: User, active: bool = True) -> List[str]:
        risks = RiskTestUtils.get_risks(user, active)
        return [o.risk_flag.name for o in risks]

    @staticmethod
    def has_risk(user: User, name: str) -> bool:
        risk_names = RiskTestUtils.get_risk_names(user)
        return name in risk_names

    @staticmethod
    def get_active_risk(user: User, name: str) -> MemberRiskFlag:
        for risk in RiskTestUtils.get_risks(user):
            if risk.risk_flag.name == name:
                return risk
        raise Exception(f"Risk is not Active {name}")
