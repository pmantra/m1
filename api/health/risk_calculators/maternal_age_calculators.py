from typing import List, Optional

from health.models.risk_enums import RiskFlagName, RiskInputKey
from health.risk_calculators.risk_calculator import InputBasedRiskCalculator
from health.risk_calculators.risk_input_repository import RiskInputRepository


class _MaternalAgeCalculator(InputBasedRiskCalculator):
    def input_keys(self) -> List[RiskInputKey]:
        return [RiskInputKey.AGE]

    def _should_member_have_risk(
        self, inputs: RiskInputRepository, required_age: int
    ) -> Optional[bool]:
        age = inputs.age()
        if not age:  # check for None/0
            return None
        return age >= required_age


class MaternalAge35PlusCalculator(_MaternalAgeCalculator):
    def risk_name(self) -> RiskFlagName:
        return RiskFlagName.ADVANCED_MATERNAL_AGE_35

    def should_member_have_risk(self, inputs: RiskInputRepository) -> Optional[bool]:
        return self._should_member_have_risk(inputs, 35)


class MaternalAge40PlusCalculator(_MaternalAgeCalculator):
    def risk_name(self) -> RiskFlagName:
        return RiskFlagName.ADVANCED_MATERNAL_AGE_40

    def should_member_have_risk(self, inputs: RiskInputRepository) -> Optional[bool]:
        return self._should_member_have_risk(inputs, 40)
