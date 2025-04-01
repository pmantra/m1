from typing import List, Optional

from health.models.risk_enums import RiskFlagName, RiskInputKey
from health.risk_calculators.risk_calculator import CompositeRiskCalculator
from health.risk_calculators.risk_input_repository import RiskInputRepository


class RiskForPretermBirthCalculator(CompositeRiskCalculator):
    def __init__(self) -> None:
        pass

    def risk_name(self) -> RiskFlagName:
        return RiskFlagName.PRETERM_LABOR_AT_RISK

    def input_keys(self) -> List[RiskInputKey]:
        return []

    def input_risks(self) -> List[RiskFlagName]:
        return [
            RiskFlagName.PRETERM_LABOR_HISTORY,
            RiskFlagName.PRETERM_LABOR_PAST_PREGNANCY,
            RiskFlagName.BLOOD_LOSS,
        ]

    # One or More of following High Risk factors
    # (name in product brief: Risk flag(s) name)
    #  Previous Preterm birth:
    #    Preterm birth - Past pregnancy
    #    History of preterm labor or delivery
    #  Short cervical length (<2.5 cm at anatomy scan):
    #    not included in mvp / data is not from assessments
    #  Significant Vaginal bleeding:
    #    blood loss
    def should_member_have_risk(self, inputs: RiskInputRepository) -> Optional[bool]:
        for name in self.input_risks():
            if inputs.has_risk(name):
                return True
        return False
