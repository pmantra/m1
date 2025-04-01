from typing import List, Optional

from maven import feature_flags

from health.models.risk_enums import RiskFlagName, RiskInputKey
from health.risk_calculators.bmi_calculators import BmiOverweightCalculator
from health.risk_calculators.risk_calculator import CompositeRiskCalculator
from health.risk_calculators.risk_input_repository import RiskInputRepository


class RiskForGestationalDiabetesCalculator(CompositeRiskCalculator):
    def __init__(self) -> None:
        self.bmi_calc = BmiOverweightCalculator()

    def risk_name(self) -> RiskFlagName:
        return RiskFlagName.GESTATIONAL_DIABETES_AT_RISK

    def input_keys(self) -> List[RiskInputKey]:
        return self.bmi_calc.input_keys()

    def input_risks(self) -> List[RiskFlagName]:
        return [
            RiskFlagName.GESTATIONAL_DIABETES_PAST_PREGNANCY,
            RiskFlagName.HIGH_BLOOD_PRESSURE,
            RiskFlagName.POLYCYSTIC_OVARIAN_SYNDROME,
            RiskFlagName.FERTILITY_TREATMENTS,
            RiskFlagName.PRETERM_LABOR_HISTORY,
            RiskFlagName.PRETERM_LABOR_PAST_PREGNANCY,
        ]

    # Must have:
    #   BMI >25 (or 23 in Asian)
    # Plus one of following:
    #    High-risk ethnicity  <-- not yet implemented
    #    Previous Gestational Diabetes
    #    Chronic Hypertension
    #    PCOS
    #    Fertility Treatment
    #    History of preterm labor or cervical issues
    def should_member_have_risk(self, inputs: RiskInputRepository) -> Optional[bool]:
        bmi = self.bmi_calc.get_bmi(inputs)
        if bmi is None:
            return None
        if feature_flags.bool_variation(
            "include-ethnicity-in-risk-calculation",
            default=False,
        ):
            racial_identity = inputs.racial_identity()
            is_asian = racial_identity == "asian"
            high_risk_races = {
                "black",
                "hispanic",
                "native_american",
                "asian",
                "pacific_islander",
            }

            # Overweight or obese (BMI >25 or >23 in Asian Americans)
            bmi_threshold = 23 if is_asian else 25

            if bmi <= bmi_threshold:
                return False

            has_other_risks = any(inputs.has_risk(name) for name in self.input_risks())

            # Return True if person has high-risk race OR any other risk factors
            # see how risks are determined in product brief
            # https://docs.google.com/document/d/1bKYMsNAD8G_FPRa1Hb1H4gomBTk-0A4-6J89WLgg8r4/edit?tab=t.0
            return racial_identity in high_risk_races or has_other_risks
        else:
            if bmi < 25:
                return False
            for name in self.input_risks():
                if inputs.has_risk(name):
                    return True
            return False
