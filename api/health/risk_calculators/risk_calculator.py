from abc import abstractmethod
from typing import Iterable, List, Optional, Union

from health.data_models.member_risk_flag import MemberRiskFlag
from health.models.risk_enums import RiskFlagName, RiskInputKey
from health.risk_calculators.risk_input_repository import RiskInputRepository


# Base Class for All Computed Risks
class RiskCalculator:
    # Name of the RiskFlag the calculator is for
    @abstractmethod
    def risk_name(self) -> RiskFlagName:
        pass


# Base Class for Risks that are calculated based on input values
# (e.g. HealthProfile fields)
class InputBasedRiskCalculator(RiskCalculator):
    # Inputs (e.g. age, weight) the calculator uses/needs
    @abstractmethod
    def input_keys(self) -> List[RiskInputKey]:
        pass

    # Should the Member have the calculator's risk_flag
    # True = Member has Risk
    # False = Member does not have risk
    # None = Unable to calculate (not enough input values)
    @abstractmethod
    def should_member_have_risk(self, inputs: RiskInputRepository) -> Optional[bool]:
        pass

    # Utility Functions Below
    # True if any of the keys are in this Calculator's input_keys
    def uses_inputs(self, keys: Iterable[RiskInputKey]) -> bool:
        return any(i in keys for i in self.input_keys())


# Base Class for Risks that are composed of other Risks, and optionally also on input values
class CompositeRiskCalculator(InputBasedRiskCalculator):
    # Risks this Composite Risk depends on
    @abstractmethod
    def input_risks(self) -> List[RiskFlagName]:
        pass

    def uses_risk(self, risk: Union[str, None]) -> bool:
        if risk is None:
            return False
        return risk in self.input_risks()

    # True if any of the risks are in this Calculator's input_risks
    def uses_risks(self, risks: Iterable[str]) -> bool:
        return any(i in risks for i in self.input_risks())


# Base class for Risks that update value over time
class TimeBasedRiskCalculator(RiskCalculator):
    # None = Do not Modify
    # int = Updated Value
    @abstractmethod
    def get_updated_risk_value(
        self, existing: MemberRiskFlag, inputs: RiskInputRepository
    ) -> Optional[int]:
        pass
