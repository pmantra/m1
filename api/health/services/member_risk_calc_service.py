import traceback
from collections.abc import Set
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from maven import feature_flags
from rq.timeouts import JobTimeoutException
from sqlalchemy.exc import InvalidRequestError, StatementError

from health.models.risk_enums import RiskInputKey
from health.risk_calculators.bmi_calculators import (
    BmiObesityCalculator,
    BmiOverweightCalculator,
)
from health.risk_calculators.high_risk_for_preeclampsia_calculator import (
    HighRiskForPreeclampsiaCalculator,
)
from health.risk_calculators.maternal_age_calculators import (
    MaternalAge35PlusCalculator,
    MaternalAge40PlusCalculator,
)
from health.risk_calculators.moderate_risk_for_preeclampsia_calculator import (
    ModerateRiskForPreeclampsiaCalculator,
)
from health.risk_calculators.months_ttc_calculator import (
    MonthsTryingToConceiveCalculator,
)
from health.risk_calculators.risk_calculator import (
    CompositeRiskCalculator,
    InputBasedRiskCalculator,
    RiskCalculator,
    TimeBasedRiskCalculator,
)
from health.risk_calculators.risk_for_gestational_diabetes_calculator import (
    RiskForGestationalDiabetesCalculator,
)
from health.risk_calculators.risk_for_preterm_birth_calculator import (
    RiskForPretermBirthCalculator,
)
from health.risk_calculators.risk_input_repository import RiskInputRepository
from health.services.member_risk_service import MemberRiskService
from utils.log import logger

log = logger(__name__)


@dataclass
class RunCalculatorsResult:
    risks_added: List[str] = field(default_factory=list)
    risks_ended: List[str] = field(default_factory=list)
    risks_updated: List[str] = field(default_factory=list)
    error_count: int = 0


# Runs RiskCalculators and updates MemberRiskFlags accordingly (sets or clears member risks)
class MemberRiskCalcService:
    @staticmethod
    def all_calculators() -> List[RiskCalculator]:
        # Note: It's important that the Composite Risk Calculators are in dependency order
        # i.e. if Risks A and B are both Composite Risks, and B uses A in its calculation
        # Then A needs to be before B so that A is updated when B runs
        return [
            #  Risks that are not Composite (only based on inputs, not on other Risks)
            MaternalAge35PlusCalculator(),
            MaternalAge40PlusCalculator(),
            BmiOverweightCalculator(),
            BmiObesityCalculator(),
            # Composite Risks with Dependencies to only non-calculated risks
            HighRiskForPreeclampsiaCalculator(),
            RiskForPretermBirthCalculator(),
            # Composite Risks with Dependencies to calculated risks but not to other composite risks
            RiskForGestationalDiabetesCalculator(),
            ModerateRiskForPreeclampsiaCalculator(),
            # Time-Based Risk Value Updates
            MonthsTryingToConceiveCalculator(),
        ]

    def __init__(
        self,
        member_risk_service: MemberRiskService,
        # Provide if already loaded, otherwise will be queried for if needed
        active_track_names: Optional[List[str]] = None,
    ):
        self.member_risk_service = member_risk_service
        self.health_profile = member_risk_service.health_profile
        self.active_track_names = active_track_names

    # Run only the Calculators that are relevant to the updates
    def run_for_updates(
        self,
        updated_values: Dict[RiskInputKey, Any],
        updated_risk: Union[str, None] = None,
    ) -> RunCalculatorsResult:
        result = RunCalculatorsResult()
        inputs = RiskInputRepository(
            self.member_risk_service,
            updated_values,
            self.health_profile,
            self.active_track_names,
        )
        calculators = self.all_calculators()
        for calc in calculators:
            if self.should_run(calc, updated_values, updated_risk, result):
                self._run_calc(calc, inputs, result)
        return result

    # Run All Calculators
    def run_all(self) -> RunCalculatorsResult:
        result = RunCalculatorsResult()
        inputs = RiskInputRepository(
            self.member_risk_service, {}, self.health_profile, self.active_track_names
        )
        calculators = self.all_calculators()
        for calc in calculators:
            self._run_calc(calc, inputs, result)
        return result

    def _run_calc(
        self,
        calc: RiskCalculator,
        inputs: RiskInputRepository,
        result: RunCalculatorsResult,
    ) -> None:
        split_cron_in_half_enabled = feature_flags.bool_variation(
            "split-nightly-risk-calculation-cron-into-half",
            default=False,
        )

        try:
            if isinstance(calc, InputBasedRiskCalculator):
                self._run_inputbased(calc, inputs, result)
            elif isinstance(calc, TimeBasedRiskCalculator):
                self._run_timebased(calc, inputs, result)
        except (InvalidRequestError, StatementError, JobTimeoutException) as db_error:
            # Database transaction errors need special handling
            result.error_count += 1
            log.error(
                "Database error occurred while running risk calculator",
                error=str(db_error),
                exc=traceback.format_exc(),
            )
            # raise database errors to trigger transaction rollback
            if split_cron_in_half_enabled:
                raise
        except Exception as e:
            result.error_count += 1
            # Log & Ignore errors
            log.error(
                "Exception occurred running risk calculator",
                error=str(e),
                exc=traceback.format_exc(),
            )

    def _run_inputbased(
        self,
        calc: InputBasedRiskCalculator,
        inputs: RiskInputRepository,
        result: RunCalculatorsResult,
    ) -> None:
        risk_name = calc.risk_name().value
        should_have_risk = calc.should_member_have_risk(inputs)
        if should_have_risk is None:
            pass  # not sure if member should have risk or not
        if should_have_risk is False:
            clear_result = self.member_risk_service.clear_risk(risk_name, False)
            if clear_result.ended_risk:
                result.risks_ended.append(risk_name)
        if should_have_risk is True:
            set_result = self.member_risk_service.set_risk(risk_name, None, False)
            if set_result.created_risk:
                result.risks_added.append(risk_name)

    def _run_timebased(
        self,
        calc: TimeBasedRiskCalculator,
        inputs: RiskInputRepository,
        result: RunCalculatorsResult,
    ) -> None:
        risk_name = calc.risk_name().value
        existing = self.member_risk_service.get_active_risk(risk_name)
        if existing is None:
            return  # no active risk to update
        if existing.id is None:
            # Ideally time-based updates should not run on new-uncommitted risks
            # although it looks like by the time this code runs, uncommitted risks
            # have been flushed and have received an id
            return
        value = calc.get_updated_risk_value(existing, inputs)
        if value is not None and value != existing.value:
            self.member_risk_service.set_risk(risk_name, value)
            result.risks_updated.append(risk_name)

    # Filter Calculators to those using any of the input keys
    @staticmethod
    def get_relevant_calculators(keys: Set[RiskInputKey]) -> List[RiskCalculator]:
        items: List[RiskCalculator] = []
        for calc in MemberRiskCalcService.all_calculators():
            if isinstance(calc, InputBasedRiskCalculator):
                if calc.uses_inputs(keys):
                    items.append(calc)
        return items

    @staticmethod
    def should_run(
        calc: RiskCalculator,
        updated_values: Dict[RiskInputKey, Any],
        updated_risk: Union[str, None],
        result_so_far: RunCalculatorsResult,
    ) -> bool:
        # Check if Input-Based Calc uses this updated value
        if isinstance(calc, InputBasedRiskCalculator):
            if calc.uses_inputs(updated_values.keys()):
                return True
        # Check if any modified Risks are an input into this Composite CalcU
        if isinstance(calc, CompositeRiskCalculator):
            if (
                calc.uses_risk(updated_risk)
                or calc.uses_risks(result_so_far.risks_added)
                or calc.uses_risks(result_so_far.risks_ended)
            ):
                return True
        return False
