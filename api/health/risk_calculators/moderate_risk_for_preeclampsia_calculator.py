from typing import List, Optional

from maven import feature_flags

from health.models.risk_enums import RiskFlagName, RiskInputKey
from health.risk_calculators.risk_calculator import CompositeRiskCalculator
from health.risk_calculators.risk_input_repository import RiskInputRepository

MODERATE_RISK_RACIAL_IDENTITY = "black"
from utils.log import logger

log = logger(__name__)


class ModerateRiskForPreeclampsiaCalculator(CompositeRiskCalculator):
    def __init__(self) -> None:
        pass

    def risk_name(self) -> RiskFlagName:
        return RiskFlagName.PREECLAMPSIA_MODERATE

    def input_keys(self) -> List[RiskInputKey]:
        return [RiskInputKey.RACIAL_IDENTITY]

    def input_risks(self) -> List[RiskFlagName]:
        return [
            RiskFlagName.PRETERM_LABOR_PAST_PREGNANCY,
            RiskFlagName.FULLTERM_LABOR_PAST_PREGNANCY,
            RiskFlagName.CSECTION_PAST_PREGNANCY,
            RiskFlagName.BMI_OBESITY,
            RiskFlagName.ADVANCED_MATERNAL_AGE_35,
            RiskFlagName.INFERTILITY_DIAGNOSIS,
            RiskFlagName.LOW_SOCIOECONOMIC_STATUS,
        ]

    # Two or More of following factor categories
    # (name in product brief: Risk flag(s) name)
    #  Nulliparity:
    #    Preterm birth - Past pregnancy
    #    Fullterm birth - Past pregnancy
    #    C-section delivery - Past pregnancy)
    #  Obesity:
    #    Obesity
    #  Maternal age >35:
    #    Advanced Maternal Age
    #  Infertility diagnosis:
    #    Unexplained infertility
    #  Sociodemographic characteristics:
    #    low socioeconomic status
    #    African American race - Not yet Implemented
    def should_member_have_risk(self, inputs: RiskInputRepository) -> Optional[bool]:
        num_factors = 0
        nulliparity = [
            RiskFlagName.PRETERM_LABOR_PAST_PREGNANCY,
            RiskFlagName.FULLTERM_LABOR_PAST_PREGNANCY,
            RiskFlagName.CSECTION_PAST_PREGNANCY,
        ]
        low_economic_status = [
            RiskFlagName.LOW_SOCIOECONOMIC_STATUS,
            RiskFlagName.SDOH_FOOD,
            RiskFlagName.SDOH_HOUSING,
            RiskFlagName.SDOH_MEDICINE,
        ]
        fertility_diagnosis = [
            RiskFlagName.INFERTILITY_DIAGNOSIS,
            RiskFlagName.FERTILITY_TREATMENTS,
        ]

        if inputs.has_any_risk(nulliparity) is False:
            num_factors += 1
        if inputs.has_risk(RiskFlagName.BMI_OBESITY):
            num_factors += 1
        if inputs.has_risk(RiskFlagName.ADVANCED_MATERNAL_AGE_35):
            num_factors += 1
        if inputs.has_any_risk(fertility_diagnosis):
            num_factors += 1
        if inputs.has_any_risk(low_economic_status):
            num_factors += 1
        if feature_flags.bool_variation(
            "include-ethnicity-in-risk-calculation",
            default=False,
        ):
            racial_identity = inputs.racial_identity()
            if racial_identity == MODERATE_RISK_RACIAL_IDENTITY:
                num_factors += 1
        return num_factors >= 2
