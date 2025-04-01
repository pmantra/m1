from typing import List, Optional

from health.models.risk_enums import RiskFlagName, RiskInputKey
from health.risk_calculators.risk_calculator import InputBasedRiskCalculator
from health.risk_calculators.risk_input_repository import RiskInputRepository
from utils.data import calculate_bmi


class BmiCalculator(InputBasedRiskCalculator):
    def input_keys(self) -> List[RiskInputKey]:
        return [RiskInputKey.HEIGHT_IN, RiskInputKey.WEIGHT_LB]

    @staticmethod
    def get_bmi(inputs: RiskInputRepository) -> Optional[float]:
        height = inputs.height()
        weight = inputs.weight()
        if not height or not weight:  # check for None/0
            return None
        return calculate_bmi(height, weight)


class BmiOverweightCalculator(BmiCalculator):
    def risk_name(self) -> RiskFlagName:
        return RiskFlagName.BMI_OVERWEIGHT

    def should_member_have_risk(self, inputs: RiskInputRepository) -> Optional[bool]:
        bmi = self.get_bmi(inputs)
        if bmi is None:
            return None
        return 25.0 <= bmi < 30.0


class BmiObesityCalculator(BmiCalculator):
    def risk_name(self) -> RiskFlagName:
        return RiskFlagName.BMI_OBESITY

    def should_member_have_risk(self, inputs: RiskInputRepository) -> Optional[bool]:
        bmi = self.get_bmi(inputs)
        if bmi is None:
            return None
        return 30.0 <= bmi
