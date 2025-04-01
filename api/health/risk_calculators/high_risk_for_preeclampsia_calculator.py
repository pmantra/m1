from typing import List, Optional

from health.models.risk_enums import RiskFlagName, RiskInputKey
from health.risk_calculators.risk_calculator import CompositeRiskCalculator
from health.risk_calculators.risk_input_repository import RiskInputRepository


class HighRiskForPreeclampsiaCalculator(CompositeRiskCalculator):
    def __init__(self) -> None:
        pass

    def risk_name(self) -> RiskFlagName:
        return RiskFlagName.PREECLAMPSIA_HIGH

    def input_keys(self) -> List[RiskInputKey]:
        return []

    def input_risks(self) -> List[RiskFlagName]:
        return [
            RiskFlagName.HIGH_BLOOD_PRESSURE_PAST_PREGNANCY,
            RiskFlagName.PREECLAMPSIA_PAST_PREGNANCY,
            RiskFlagName.ECLAMPSIA_PAST_PREGNANCY,
            RiskFlagName.MULTIPLE_GESTATION,
            RiskFlagName.HIGH_BLOOD_PRESSURE,
            RiskFlagName.DIABETES,
            RiskFlagName.DIABETES_EXISTING,
            RiskFlagName.GESTATIONAL_DIABETES_CURRENT_PREGNANCY,
            RiskFlagName.KIDNEY_DISEASE,
            RiskFlagName.KIDNEY_DISEASE_EXISTING,
            RiskFlagName.AUTOIMMUNE_DISEASE,
            RiskFlagName.AUTOIMMUNE_DISEASE_EXISTING,
        ]

    # One or More of following High Risk factors
    # (name in product brief: Risk flag(s) name)
    #   Previous Pregnancy Risk:
    #     High blood pressure - Past pregnancy
    #     Preeclampsia - Past pregnancy
    #     Eclampsia or HELLP - Past pregnancy
    #   Multiple gestation:
    #     Multiple gestation
    #   Chronic Hypertension:
    #     High blood pressure - Existing condition
    #   Type 1 or 2 Diabetes:
    #     Diabetes
    #     Diabetes - Existing condition
    #   Gestational Diabetes:
    #     Gestational diabetes - Current pregnancy
    #   Kidney Disease:
    #     Kidney disease
    #     Kidney disease - Existing condition
    #   Autoimmune Disease:
    #     Autoimmune disease
    #     Autoimmune disease - Existing condition
    def should_member_have_risk(self, inputs: RiskInputRepository) -> Optional[bool]:
        for name in self.input_risks():
            if inputs.has_risk(name):
                return True
        return False
