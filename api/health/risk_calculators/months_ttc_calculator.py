from datetime import date, datetime
from typing import Optional

from dateutil.relativedelta import relativedelta

from health.data_models.member_risk_flag import MemberRiskFlag
from health.models.risk_enums import RiskFlagName
from health.risk_calculators.risk_calculator import TimeBasedRiskCalculator
from health.risk_calculators.risk_input_repository import RiskInputRepository
from models.tracks.track import TrackName
from utils.log import logger

log = logger(__name__)


class MonthsTryingToConceiveCalculator(TimeBasedRiskCalculator):
    def __init__(self) -> None:
        pass

    def risk_name(self) -> RiskFlagName:
        return RiskFlagName.MONTHS_TRYING_TO_CONCEIVE

    def get_updated_risk_value(
        self, existing: MemberRiskFlag, inputs: RiskInputRepository
    ) -> Optional[int]:
        # Make sure user is in fertility track
        # TODO: And check fertility treatment status based on the rules in the product brief
        if not inputs.has_track(TrackName.FERTILITY):
            return None

        if existing.value is None:
            log.error(
                "Risk should have value but didn't. Setting value to 0",
                risk=RiskFlagName.MONTHS_TRYING_TO_CONCEIVE.value,
                user_id=existing.user_id,
            )
            return 0

        additional_months = self.convert_date_to_months_since(
            existing.created_at.date()
        )
        if additional_months == 0:
            return None
        return existing.value + additional_months

    @staticmethod
    def convert_date_to_months_since(start: date) -> int:
        # this will round down, ie 0-30/31 days = 0 months
        today = datetime.today()
        r = relativedelta(today, start)
        months = (r.years * 12) + r.months
        if months < 0:
            log.error(
                "Start date is in the future, using months=0",
                context={"start": start.isoformat()},
            )
            months = 0
        return months
