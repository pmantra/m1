from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from cost_breakdown.constants import Tier
from cost_breakdown.models.rte import RTETransaction, TieredRTEErrorData
from wallet.models.constants import FamilyPlanType
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan


class ImprovableException(ABC):
    @abstractmethod
    def get_internal_message(self) -> str:
        pass

    @abstractmethod
    def get_format_kwargs(self) -> dict:
        pass


class CostBreakdownException(Exception):
    ...


class CostBreakdownCalculatorValidationError(CostBreakdownException, ValueError):
    pass


class ActionableCostBreakdownException(CostBreakdownException):
    def __init__(self, message: str):
        self.message = message

    def __repr__(self) -> str:
        return f"Need Ops Action: {self.message}"

    __str__ = __repr__


class TieredConfigurationError(ActionableCostBreakdownException):
    pass


class TieredRTEError(ActionableCostBreakdownException, ImprovableException):
    def __init__(
        self,
        message: str,
        tier: Optional[Tier],
        errors: List[TieredRTEErrorData],
        plan: EmployerHealthPlan,
    ):
        super().__init__(message)
        self.tier = tier
        self.errors = errors
        self.plan = plan

    def get_internal_message(self) -> str:
        msg = (
            "This calculation is for tier {tier} coverage. "
            if self.tier
            else "This calculation has a coverage error. "
        )
        # Handle a list of errors in the message.
        for error in self.errors:
            msg += (
                "The tiered coverage expects a {attr_name} of {coverage_value}, "
                "however PVerify is returning a {attr_name} of {rte_value}. "
            ).format(
                attr_name=error.attr_name,
                coverage_value=error.coverage_value,
                rte_value=error.rte_value,
            )
        msg += (
            "Please check the member is assigned to the correct employer health plan {plan}, "
            "and the employer health plan has the correct limit configurations."
        )
        return msg

    def get_format_kwargs(self) -> dict:
        kwargs: dict = {
            "plan": self.plan,
        }
        if self.tier:
            kwargs["tier"] = self.tier
        return kwargs


class NoCostSharingCategory(ActionableCostBreakdownException):
    """
    This case is handled inside the ErrorMessageImprover
    """

    pass


class NoMemberHealthPlanError(ActionableCostBreakdownException):
    def __init__(self, message: str):
        super().__init__(message)


class NoIrsDeductibleFoundError(ActionableCostBreakdownException):
    def __init__(self, message: str):
        super().__init__(message)


class NoGlobalProcedureFoundError(ActionableCostBreakdownException):
    def __init__(self, message: str):
        super().__init__(message)


class NoGlobalProcedureCostSharingCategoryFoundError(ActionableCostBreakdownException):
    def __init__(self, message: str):
        super().__init__(message)


class NoPatientNameFoundError(ActionableCostBreakdownException):
    def __init__(self, message: str):
        super().__init__(message)


class NoCostSharingFoundError(ActionableCostBreakdownException):
    def __init__(self, message: str):
        super().__init__(message)


class InvalidReimbursementCategoryIDError(ActionableCostBreakdownException):
    """No valid reimbursement_plan found for a wallet's allowed_reimbursement_categories"""

    def __init__(self, message: str):
        super().__init__(message)


# Bad Data Errors
class CostBreakdownInvalidInput(CostBreakdownException):
    pass


# Pverify Errors
class PverifyHttpCallError(CostBreakdownException, ImprovableException):
    def __init__(self, message: str, http_status: int):
        super().__init__(message)
        self.http_status = http_status

    def get_internal_message(self) -> str:
        if self.http_status == 408:
            return (
                "The request to Pverify timed out. Please wait a short time and then try again. If later attempts also "
                "fail, please reach out to @payments-platform-oncall to see if Pverify is down."
            )
        elif self.http_status == 401:
            return (
                "The request to Pverify failed authorization. Please wait a short time and then try again. "
                "If later attempts also fail, please reach out to @payments-platform-oncall to see if Pverify is down."
            )
        else:
            return (
                "The request to Pverify failed with an unexpected error. Please reach out to @payments-platform-oncall "
                "to see if Pverify is down."
            )

    def get_format_kwargs(self) -> dict:
        return {}


class PverifyProcessFailedError(ActionableCostBreakdownException, ImprovableException):
    def __init__(self, message: str, error: str, rte_transaction: RTETransaction):
        super().__init__(message)
        self.error = error
        self.rte_transaction = rte_transaction

    def _error_to_better_error(self, error_message: str) -> str:
        """
        Cconvert common error messages from Pverify to a maven-specific actionable message.
        """
        if "Invalid/Missing Provider ID" in error_message:
            return (
                "Error Reason: Invalid/Missing Provider ID. This payer may need a non-standard Maven provider id. "
                "Please pass this to Payment Ops to get RTE values from Pverify directly."
            )
        return error_message

    def get_internal_message(self) -> str:
        return "Pverify has returned the following error: {error} for RTE transaction {rte_transaction}."

    def get_format_kwargs(self) -> dict:
        return {
            "error": self._error_to_better_error(self.error),
            "rte_transaction": self.rte_transaction,
        }


class PverifyEligibilityInfoParsingError(ActionableCostBreakdownException):
    def __init__(self, message: str):
        super().__init__(message)


class PverifyPlanInactiveError(ActionableCostBreakdownException, ImprovableException):
    def __init__(self, message: str, plan: MemberHealthPlan):
        super().__init__(message)
        self.plan = plan

    def get_internal_message(self) -> str:
        return (
            "Pverify has indicated that this user’s plan {plan} is inactive. This user may be on COBRA. "
            "Please reach out to Payment Ops for a manual override using the member's last known RTE data."
        )

    def get_format_kwargs(self) -> dict:
        return {"plan": self.plan}


class NoIndividualDeductibleOopRemaining(
    ActionableCostBreakdownException, ImprovableException
):
    def __init__(
        self, message: str, plan: MemberHealthPlan, rte_transaction: RTETransaction
    ):
        super().__init__(message)
        self.plan = plan
        self.rte_transaction = rte_transaction

    def get_internal_message(self) -> str:
        """
        The plan and procedure token here will be formatted as a link to the relevant procedure.
        """
        return (
            "This user's health plan {plan} has no remaining "
            + FamilyPlanType(self.plan.plan_type).value
            + " deductible or out-of-pocket"
            " maximum according to Pverify: {rte_transaction}. Please send this to Payment Ops who can check historical"
            " data and pverify or contact the member for an accurate explanation of benefits for this {procedure}."
        )

    def get_format_kwargs(self) -> dict:
        return {"plan": self.plan, "rte_transaction": self.rte_transaction}


class NoFamilyDeductibleOopRemaining(ActionableCostBreakdownException):
    def __init__(self, message: str):
        super().__init__(message)


# Create Direct Payment Claim
class CreateDirectPaymentClaimErrorResponseException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class InvalidDirectPaymentClaimCreationRequestException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class NoRTEPayerFound(ActionableCostBreakdownException):
    def __init__(self, message: str):
        super().__init__(message)


class WalletBalanceReimbursementsException(Exception):
    ...


class UnsupportedTreatmentProcedureException(Exception):
    ...


class CostBreakdownDatabaseException(CostBreakdownException):
    ...


class PayerDisabledCostBreakdownException(CostBreakdownException):
    ...
