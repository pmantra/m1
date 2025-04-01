import datetime
from typing import Optional

import sqlalchemy
from maven import feature_flags

from cost_breakdown.models.cost_breakdown import (
    CostBreakdown,
    ReimbursementRequestToCostBreakdown,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.errors import (
    AccumulationAdjustmentNeeded,
    InvalidAccumulationMappingData,
)
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_list import Payer
from utils.log import logger
from wallet.models.constants import (
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestState,
    ReimbursementRequestType,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan, ReimbursementWallet
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    OLD_BEHAVIOR,
    HealthPlanRepository,
)

log = logger(__name__)


class AccumulationMappingService:
    def __init__(self, session: sqlalchemy.orm.Session):
        self.session = session

    @staticmethod
    def reimbursement_request_is_valid_for_accumulation(
        reimbursement_request: ReimbursementRequest,
    ) -> bool:
        """
        Checks the validity of reimbursement requests across all cases where we accumulate them.
        """
        has_member_data = (
            reimbursement_request.person_receiving_service_id is not None
            and reimbursement_request.person_receiving_service_member_status == "MEMBER"
        )
        has_request_data = (
            reimbursement_request.procedure_type is not None
            and reimbursement_request.cost_sharing_category is not None
        )
        is_manual = (
            reimbursement_request.reimbursement_type == ReimbursementRequestType.MANUAL
        )
        is_mmb = (
            reimbursement_request.wallet.reimbursement_organization_settings.direct_payment_enabled
        )

        # combine all cases
        is_valid_reimbursement_request = (
            is_manual and has_member_data and has_request_data and is_mmb
        )
        if is_valid_reimbursement_request:
            has_cost_breakdown = (
                CostBreakdown.query.filter(
                    CostBreakdown.reimbursement_request_id == reimbursement_request.id
                ).count()
                > 0
            )
            if not has_cost_breakdown:
                log.error(
                    "Skipping Accumulating a valid mmb reimbursement request due to lack of cost breakdown.",
                    reimbursement_request_id=str(reimbursement_request.id),
                )
                return False
        else:
            log.info(
                "Skipping accumulating an invalid mmb request",
                reimbursement_request_id=str(reimbursement_request.id),
                has_member_data=has_member_data,
                has_request_data=has_request_data,
                is_manual=is_manual,
                is_mmb=is_mmb,
            )
        return is_valid_reimbursement_request

    @staticmethod
    def should_accumulate_reimbursement_request_pre_approval(
        reimbursement_request: ReimbursementRequest, cost_breakdown: CostBreakdown
    ) -> bool:
        """
        For the one case where we accumulate without Peak One approval involved
        """
        is_deductible_accumulation = (
            reimbursement_request.wallet.reimbursement_organization_settings.deductible_accumulation_enabled
        )
        if (
            reimbursement_request.amount == cost_breakdown.total_member_responsibility
            and is_deductible_accumulation is True
            and reimbursement_request.state == ReimbursementRequestState.DENIED
        ):
            return True
        return False

    @staticmethod
    def should_accumulate_reimbursement_request_post_approval(
        reimbursement_request: ReimbursementRequest, cost_breakdown: CostBreakdown
    ) -> bool:
        """
        Indicator of accumulate_reimbursement_request_post_approval running after Peak One actions
        Conditional for including a message in the reimbursement request calculator save message.
        Needs to come after ReimbursementRequestService.update_reimbursement_request_for_cost_breakdown
        """
        if AccumulationMappingService._post_approval_deductible_accumulation_case(
            reimbursement_request, cost_breakdown
        ):
            return True
        return False

    @staticmethod
    def _post_approval_deductible_accumulation_case(
        reimbursement_request: ReimbursementRequest, cost_breakdown: CostBreakdown
    ) -> bool:
        is_deductible_accumulation = (
            reimbursement_request.wallet.reimbursement_organization_settings.deductible_accumulation_enabled
        )
        return (
            reimbursement_request.amount == cost_breakdown.total_employer_responsibility
            and cost_breakdown.total_member_responsibility > 0
            and is_deductible_accumulation is True
        )

    def accumulate_reimbursement_request_post_approval(
        self, reimbursement_request: ReimbursementRequest, cost_breakdown: CostBreakdown
    ) -> Optional[AccumulationTreatmentMapping]:
        """
        In some cases, an accumulation should be recorded when a reimbursement request goes through a state change.
        This only applies to reimbursement requests with cost breakdowns.
        There is also one case where we accumulate in update_reimbursement_request_for_cost_breakdown directly.
        """
        if (
            AccumulationMappingService._post_approval_deductible_accumulation_case(
                reimbursement_request, cost_breakdown
            )
            and reimbursement_request.state == ReimbursementRequestState.APPROVED
        ):
            # If member responsibility is some of the amount, for DA, we've set amount to employer responsibility
            # 1) Peak One approves towards HRA,
            # 2) RR is updated to Approved in our system automatically
            # 3) Member Responsibility should be submitted for accumulation
            return self.create_valid_reimbursement_request_mapping(
                reimbursement_request=reimbursement_request
            )
        return None

    def create_valid_reimbursement_request_mapping(
        self, reimbursement_request: ReimbursementRequest
    ) -> AccumulationTreatmentMapping:
        """
        Note that this function does not *commit* the mapping after creation.
        """
        payer = None
        try:
            # check if there are any previous mappings and this is an adjustment
            existing_mappings = AccumulationTreatmentMapping.query.filter(
                AccumulationTreatmentMapping.reimbursement_request_id
                == reimbursement_request.id
            ).all()
            if existing_mappings:
                if (
                    reimbursement_request.auto_processed
                    != ReimbursementRequestAutoProcessing.RX
                ):
                    # TODO: implement automatic adjustments
                    raise AccumulationAdjustmentNeeded(
                        "There are pre-existing accumulation mappings for this Reimbursement Request. "
                        "Adjustments to reimbursement accumulation are currently manual only."
                    )
                elif not all(
                    mapping.treatment_accumulation_status
                    == TreatmentAccumulationStatus.REFUNDED
                    for mapping in existing_mappings
                ):
                    raise AccumulationAdjustmentNeeded(
                        "There are pre-existing accumulation mappings for this auto-processed RX Reimbursement Request. "
                        "Adjustments must all be in the REFUNDED status to proceed."
                    )

            # avoid double accumulations for treatment procedures
            procedure_associations_count = (
                ReimbursementRequestToCostBreakdown.query.filter(
                    ReimbursementRequestToCostBreakdown.reimbursement_request_id
                    == reimbursement_request.id
                ).count()
            )
            if procedure_associations_count > 0:
                raise InvalidAccumulationMappingData(
                    "This Reimbursement Request is associated with a Treatment Procedure's Cost Breakdown. "
                    "It should only be accumulated at the Treatment Procedure level."
                )

            # validate that the request belongs to a report
            if reimbursement_request.person_receiving_service_id is None:
                raise InvalidAccumulationMappingData(
                    "Missing the Person Receiving Service ID for payer accumulation. "
                    "This field is required for determining the associated member health plan."
                )
            payer = self.get_valid_payer(
                reimbursement_wallet_id=reimbursement_request.reimbursement_wallet_id,
                user_id=reimbursement_request.person_receiving_service_id,
                procedure_type=TreatmentProcedureType(
                    reimbursement_request.procedure_type
                ),
                effective_date=reimbursement_request.service_start_date,
            )

            # object-level validation + creating the new mapping for the new request accumulation
            mapping = self.mapping_from_reimbursement_request(
                reimbursement_request=reimbursement_request,
                payer_id=payer.id,
            )
        except InvalidAccumulationMappingData as e:
            log.error(
                "Failed to add a reimbursement request to payer accumulation report.",
                error_message=str(e),
                reimbursement_request_id=str(
                    reimbursement_request.id
                ),  # str due to datadog handling of BIGINTs
                payer_id=payer.id if payer else None,
                expected_payer_id=e.expected_payer_id,
            )
            raise e
        return mapping

    def mapping_from_reimbursement_request(
        self,
        reimbursement_request: ReimbursementRequest,
        payer_id: int,
    ) -> AccumulationTreatmentMapping:
        if reimbursement_request.reimbursement_type != ReimbursementRequestType.MANUAL:
            raise InvalidAccumulationMappingData(
                "Invalid ReimbursementRequestType for payer accumulation. Must be MANUAL."
            )

        if reimbursement_request.state not in [
            ReimbursementRequestState.APPROVED,
            ReimbursementRequestState.DENIED,
        ]:
            log.error(
                "Invalid ReimbursementRequestState for payer accumulation.",
                state=reimbursement_request.state,
                reimbursement_request=str(
                    reimbursement_request.id
                ),  # str due to datadog handling of BIGINTs
            )
            raise InvalidAccumulationMappingData(
                "Invalid ReimbursementRequestState for payer accumulation. Must be one of APPROVED or DENIED."
            )

        return AccumulationTreatmentMapping(
            treatment_procedure_uuid=None,
            reimbursement_request_id=reimbursement_request.id,
            # All reimbursement requests have been paid before being submitted.
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
            completed_at=reimbursement_request.created_at,
            payer_id=payer_id,
            is_refund=False,
            # deductible and oop will be added during the file generation to stay in sync with the current mapping flow
        )

    def get_valid_payer(
        self,
        reimbursement_wallet_id: int,
        user_id: int,
        procedure_type: TreatmentProcedureType,
        effective_date: datetime.datetime,
    ) -> Payer:
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != OLD_BEHAVIOR
        ):
            health_plan_repo = HealthPlanRepository(session=self.session)
            employer_health_plan = (
                health_plan_repo.get_employer_plan_by_wallet_and_member_id(
                    wallet_id=reimbursement_wallet_id,
                    member_id=user_id,
                    effective_date=effective_date,
                )
            )
        else:
            employer_health_plan = (
                EmployerHealthPlan.query.join(  # noqa
                    MemberHealthPlan,
                    MemberHealthPlan.employer_health_plan_id == EmployerHealthPlan.id,
                )
                .join(
                    ReimbursementWallet,
                    ReimbursementWallet.id == MemberHealthPlan.reimbursement_wallet_id,
                )
                .filter(
                    ReimbursementWallet.id == reimbursement_wallet_id,
                    MemberHealthPlan.member_id == user_id,
                )
                .one_or_none()
            )
        if employer_health_plan is None:
            log.error(
                "No Employer Health plan found for this user and this wallet.",
                wallet_id=str(reimbursement_wallet_id),
                user_id=str(user_id),
                effective_date=effective_date,
            )
            raise InvalidAccumulationMappingData(
                "No Employer Health plan found for this user and this wallet on the given effective date."
            )
        if (
            procedure_type == TreatmentProcedureType.PHARMACY
            and employer_health_plan.rx_integrated is False
        ):
            # Get RX Integrated payer instead of default payer. Change hardcoding of ESI in the future.
            payer = Payer.query.filter(Payer.payer_name == PayerName.ESI).one_or_none()
        else:
            payer = Payer.query.get(employer_health_plan.benefits_payer_id)
        if payer is None:
            log.error(
                "No payer found when attempting to add an accumulation mapping.",
                wallet_id=str(reimbursement_wallet_id),
                user_id=str(user_id),
                expected_payer_id=employer_health_plan.benefits_payer_id,
                procedure_type=procedure_type.value,
            )
            raise InvalidAccumulationMappingData(
                "No associated Payer found. Check Member and Employer health plan configurations.",
                expected_payer_id=employer_health_plan.benefits_payer_id,
            )
        try:
            # Payer must have an accumulation report associated
            PayerName(payer.payer_name)
        except ValueError:
            raise InvalidAccumulationMappingData(
                "The Associated Payer is not accumulation-report enabled. "
                "Check Member and Employer health plan configurations.",
                expected_payer_id=employer_health_plan.benefits_payer_id,
            )
        return payer

    def update_status_to_accepted(
        self, accumulation_unique_id: str, response_status: str, response_code: str
    ) -> bool:
        return self._update_status_with_response(
            status=TreatmentAccumulationStatus.ACCEPTED,
            accumulation_unique_id=accumulation_unique_id,
            response_status=response_status,
            response_code=response_code,
        )

    def update_status_to_rejected(
        self, accumulation_unique_id: str, response_status: str, response_code: str
    ) -> bool:
        return self._update_status_with_response(
            status=TreatmentAccumulationStatus.REJECTED,
            accumulation_unique_id=accumulation_unique_id,
            response_status=response_status,
            response_code=response_code,
        )

    def _update_status_with_response(
        self,
        status: TreatmentAccumulationStatus,
        accumulation_unique_id: str,
        response_status: str,
        response_code: str,
    ) -> bool:
        context = {
            "accumulation_unique_id": accumulation_unique_id,
            "response_status": response_status,
            "response_code": response_code,
        }
        try:
            acc_treatment_mapping = (
                self.session.query(AccumulationTreatmentMapping)
                .filter(
                    AccumulationTreatmentMapping.accumulation_unique_id
                    == accumulation_unique_id
                )
                .one_or_none()
            )
            if acc_treatment_mapping:
                acc_treatment_mapping.treatment_accumulation_status = status  # type: ignore[assignment] # Incompatible types in assignment (expression has type "TreatmentAccumulationStatus", variable has type "str | None")
                acc_treatment_mapping.response_code = response_code
                self.session.add(acc_treatment_mapping)
                self.session.commit()
                return True
            else:
                log.error(
                    "AccumulationTreatmentMapping not found with associated accumulation_unique_id.",
                    **context,
                )
        except Exception as e:
            log.exception(
                f"Error occurred while updating treatment accumulation status to '{status.value}'.",
                error=e,
                **context,
            )
            self.session.rollback()

        return False
