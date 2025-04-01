from __future__ import annotations

import dataclasses
from datetime import date, datetime
from typing import Dict, List, Optional

import sqlalchemy as sa
from maven import feature_flags

from audit_log.utils import emit_audit_log_create, get_flask_admin_user
from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.models import Bill
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from payer_accumulator import helper_functions
from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.errors import RefundTreatmentAccumulationError
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from utils.log import logger
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlan,
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import MemberHealthPlan
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    NEW_BEHAVIOR,
    OLD_BEHAVIOR,
    HealthPlanRepository,
)

log = logger(__name__)


@dataclasses.dataclass
class ProcedureToAccumulationData:
    status: TreatmentAccumulationStatus
    completed_date: Optional[datetime]
    wallet_id: int
    member_id: int
    start_date: Optional[date]


class AccumulationDataSourcer:
    def __init__(self, payer_name: PayerName, session: sa.orm.Session = None):  # type: ignore[assignment]
        self.payer_name: PayerName = payer_name
        self.payer_id: int = helper_functions.get_payer_id(
            payer_name=payer_name, log=log
        )
        self.session = session
        self.treatment_procedure_repo = TreatmentProcedureRepository(self.session)  # type: ignore[arg-type]
        self.billing_service = BillingService(session=self.session)  # type: ignore[arg-type]
        self.health_plan_repo = HealthPlanRepository(session=self.session)

    def data_source_preparation_for_file_generation(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self._insert_new_data_for_generation()
        self._update_waiting_data_for_generation()

    def revert_treatment_accumulation(
        self, procedure: TreatmentProcedure
    ) -> Optional[AccumulationTreatmentMapping]:
        """
        This will fully revert payer accumulation for a treatment procedure, partial reversal is currently not supported
        if the previous accumulation has been picked up by file generator, a new REFUNDED mapping row will be created,
        which will be later picked up by file generator and sent to payer.
        if it's not picked up by file generator yet, then set them to SKIP instead.
        Also idempotency is important, meaning the payer accumulation can only be reverted once.
        """
        mappings = (
            self.session.query(
                AccumulationTreatmentMapping  # type: ignore[union-attr] # Item "None" of "Optional[Session]" has no attribute "query"
            )
            .filter(
                AccumulationTreatmentMapping.treatment_procedure_uuid == procedure.uuid,
            )
            .all()
        )
        mappings_sent_to_payer = [
            mapping
            for mapping in mappings
            if mapping.treatment_accumulation_status
            in {
                TreatmentAccumulationStatus.PROCESSED,
                TreatmentAccumulationStatus.SUBMITTED,
                TreatmentAccumulationStatus.ACCEPTED,
            }
        ]

        refund_mapping = [
            mapping
            for mapping in mappings
            if mapping.treatment_accumulation_status
            == TreatmentAccumulationStatus.REFUNDED
        ]
        if not mappings_sent_to_payer:
            for mapping in mappings:
                mapping.treatment_accumulation_status = TreatmentAccumulationStatus.SKIP  # type: ignore[assignment] # Incompatible types in assignment (expression has type "TreatmentAccumulationStatus", variable has type "Optional[str]")
                log.info(
                    "Treatment accumulation not sent to payer yet, update all existing mappings to skip status",
                    mapping_id=mapping.id,
                )
            self.session.commit()  # type: ignore[union-attr] # Item "None" of "Optional[Session]" has no attribute "commit"
            return None

        # skip when there is existing refund mapping or the refund mapping has already been submitted to payer
        deductible_sent = sum(m.deductible for m in mappings_sent_to_payer)
        oop_sent = sum(m.oop_applied for m in mappings_sent_to_payer)
        hra_sent = sum(
            m.hra_applied if m.hra_applied is not None else 0
            for m in mappings_sent_to_payer
        )
        if deductible_sent < 0 or oop_sent < 0 or hra_sent < 0:
            raise RefundTreatmentAccumulationError(
                "Cannot revert a treatment accumulation that has negative deductible or oop amount sent to payer"
            )
        if refund_mapping or (deductible_sent == 0 and oop_sent == 0 and hra_sent == 0):
            raise RefundTreatmentAccumulationError(
                "Treatment accumulation has already been fully refunded"
            )

        mapping = AccumulationTreatmentMapping(
            treatment_procedure_uuid=procedure.uuid,
            treatment_accumulation_status=TreatmentAccumulationStatus.REFUNDED,
            completed_at=procedure.completed_date,
            payer_id=self.payer_id,
            deductible=-deductible_sent,
            oop_applied=-oop_sent,
            hra_applied=-hra_sent,
            is_refund=True,
        )
        self.session.add(
            mapping
        )  # type: ignore[union-attr] # Item "None" of "Optional[Session]" has no attribute "add"
        log.info(
            "Inserted reverse treatment procedure accumulation into treatment mapping table",
            treatment_procedure_uuid=procedure.uuid,
        )
        self.session.commit()  # type: ignore[union-attr] # Item "None" of "Optional[Session]" has no attribute "commit"
        return mapping

    def _insert_new_data_for_generation(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # TODO: integration test PAY-4883
        (
            medical_wallet_ids,
            rx_wallet_ids,
        ) = self._get_medical_and_rx_accumulation_wallet_ids()
        accumulation_tp = self._get_latest_treatment_procedure_statuses(
            medical_wallet_ids=medical_wallet_ids,
            rx_wallet_ids=rx_wallet_ids,
            cutoff=None,  # type: ignore[arg-type] # Argument "cutoff" to "_get_latest_treatment_procedure_statuses" of "AccumulationDataSourcer" has incompatible type "None"; expected "datetime"
        )
        if accumulation_tp:
            self._insert_accumulation_treatment_mapping(
                accumulation_tp_mapping=accumulation_tp
            )
        else:
            log.info(f"No ready treatment procedures for {self.payer_name}")

    def _update_waiting_data_for_generation(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # TODO: integration test PAY-4883
        waiting_tp_statuses = self._get_paid_waiting_treatment_procedure_statuses()
        self._update_accumulation_treatment_mapping(
            accumulation_tp_mapping=waiting_tp_statuses
        )

    # instance level cache for _accumulation_employer_health_plans
    _cached_accumulation_employer_health_plans: list[EmployerHealthPlan] | None = None

    @property
    def _accumulation_employer_health_plans(self) -> list[EmployerHealthPlan]:
        if self._cached_accumulation_employer_health_plans:
            return self._cached_accumulation_employer_health_plans

        sql_and = sa.and_(
            EmployerHealthPlan.benefits_payer_id == self.payer_id,
            ReimbursementOrganizationSettings.deductible_accumulation_enabled
            == sa.true(),
        )
        self._cached_accumulation_employer_health_plans = (
            self.session.query(
                EmployerHealthPlan
            )  # type: ignore[union-attr] # Item "None" of "Optional[Session]" has no attribute "query"
            .join(
                ReimbursementOrganizationSettings,
                ReimbursementOrganizationSettings.id
                == EmployerHealthPlan.reimbursement_org_settings_id,
            )
            .filter(sql_and)
            .all()
        )
        return self._cached_accumulation_employer_health_plans  # type: ignore[return-value] # Incompatible return value type (got "Optional[List[EmployerHealthPlan]]", expected "List[EmployerHealthPlan]")

    def _get_medical_and_rx_accumulation_wallet_ids(self) -> (List[int], List[int]):  # type: ignore[syntax] # Syntax error in type annotation
        medical_wallet_ids = []
        rx_wallet_ids = []
        for plan in self._accumulation_employer_health_plans:
            if (
                feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
                != OLD_BEHAVIOR
            ):
                wallet_ids = (
                    self.health_plan_repo.get_all_wallet_ids_for_an_employer_plan(
                        employer_plan_id=plan.id
                    )
                )
                if not wallet_ids:
                    log.info(f"No wallets for employer_health_plan with id {plan.id}")
                else:
                    if plan.rx_integrated:
                        rx_wallet_ids.extend(wallet_ids)

                    medical_wallet_ids.extend(wallet_ids)
            else:
                wallet_ids = MemberHealthPlan.query.with_entities(
                    MemberHealthPlan.reimbursement_wallet_id
                ).filter_by(employer_health_plan_id=plan.id)
                if not wallet_ids:
                    log.info(f"No wallets for employer_health_plan with id {plan.id}")
                else:
                    if plan.rx_integrated:
                        rx_wallet_ids.extend(
                            wallet_id.reimbursement_wallet_id for wallet_id in wallet_ids  # type: ignore[attr-defined]
                        )

                    medical_wallet_ids.extend(
                        wallet_id.reimbursement_wallet_id for wallet_id in wallet_ids  # type: ignore[attr-defined]
                    )

        return medical_wallet_ids, rx_wallet_ids

    def _get_latest_accumulation_treatment_procedures(
        self,
        wallet_ids: List[int],
        cutoff: datetime,
        procedure_type: TreatmentProcedureType,
    ) -> List[TreatmentProcedure]:
        ready_tps = self.treatment_procedure_repo.get_treatments_since_datetime_from_statuses_type_wallet_ids(
            wallet_ids=wallet_ids,
            statuses=[
                TreatmentProcedureStatus.COMPLETED,
                TreatmentProcedureStatus.PARTIALLY_COMPLETED,
            ],
            procedure_type=procedure_type,
            cutoff=cutoff,
        )
        return ready_tps

    def _get_treatment_procedure_cutoff(self) -> datetime:
        latest_tp_for_payer = (
            AccumulationTreatmentMapping.query.filter(
                AccumulationTreatmentMapping.payer_id == self.payer_id
            )
            .order_by(AccumulationTreatmentMapping.completed_at.desc())
            .limit(1)
            .one_or_none()
        )
        if latest_tp_for_payer:
            tp_cutoff = latest_tp_for_payer.completed_at
            log.info(
                f"Querying for treatment procedures completed or partially completed since {tp_cutoff}"
            )
            return tp_cutoff
        else:
            log.info(
                f"No accumulation_treatment_mapping found for payer id {self.payer_id}"
            )
            log.info("Not using cut off time querying for treatment procedures")
            return None  # type: ignore[return-value] # Incompatible return value type (got "None", expected "datetime")

    def _get_latest_treatment_procedure_statuses(
        self,
        rx_wallet_ids: List[int],
        medical_wallet_ids: List[int],
        cutoff: datetime,
    ) -> Optional[Dict[str, ProcedureToAccumulationData]]:
        ready_tps = []
        if medical_wallet_ids:
            ready_tps.extend(
                self._get_latest_accumulation_treatment_procedures(
                    wallet_ids=medical_wallet_ids,
                    cutoff=cutoff,
                    procedure_type=TreatmentProcedureType.MEDICAL,
                )
            )
        if rx_wallet_ids:
            ready_tps.extend(
                self._get_latest_accumulation_treatment_procedures(
                    wallet_ids=rx_wallet_ids,
                    cutoff=cutoff,
                    procedure_type=TreatmentProcedureType.PHARMACY,
                )
            )
        if ready_tps:
            return self._get_accumulation_treatment_procedure_statuses(
                treatment_procedures=ready_tps
            )
        else:
            return None

    def _get_paid_waiting_treatment_procedure_statuses(
        self,
    ) -> Dict[str, ProcedureToAccumulationData]:
        waiting_tp_mappings = AccumulationTreatmentMapping.query.filter(
            sa.and_(
                AccumulationTreatmentMapping.payer_id == self.payer_id,
                AccumulationTreatmentMapping.treatment_accumulation_status
                == TreatmentAccumulationStatus.WAITING,
            )
        ).all()
        waiting_tp_uuids = [
            mapping.treatment_procedure_uuid for mapping in waiting_tp_mappings
        ]
        waiting_tps = self.treatment_procedure_repo.get_treatments_by_uuids(
            treatment_procedure_uuids=waiting_tp_uuids
        )
        # filter out the tps that are still waiting! we only want to update ones in our schema that have become PAID
        waiting_tp_new_statuses = self._get_accumulation_treatment_procedure_statuses(
            treatment_procedures=waiting_tps
        )
        ready_tps = {
            tp_uuid: procedure_data
            for (tp_uuid, procedure_data) in waiting_tp_new_statuses.items()
            if TreatmentAccumulationStatus.WAITING != procedure_data.status
        }
        return ready_tps

    def _get_accumulation_treatment_procedure_statuses(
        self, treatment_procedures: List[TreatmentProcedure]
    ) -> Dict[str, ProcedureToAccumulationData]:
        ready_tp_ids = [tp.id for tp in treatment_procedures]
        tp_ids_to_tps = {tp.id: tp for tp in treatment_procedures}
        tp_id_to_bills = self.billing_service.get_member_paid_by_procedure_ids(
            procedure_ids=ready_tp_ids
        )
        accumulation_tp_map = dict()
        for tp_id, tp in tp_ids_to_tps.items():
            bills = tp_id_to_bills.get(tp_id) or []
            tp_accumulation_status = self._determine_tp_accumulation_status(tp, bills)
            accumulation_tp_map[tp.uuid] = ProcedureToAccumulationData(
                status=tp_accumulation_status,
                completed_date=tp.completed_date,
                wallet_id=tp.reimbursement_wallet_id,
                member_id=tp.member_id,
                start_date=tp.start_date,
            )
        return accumulation_tp_map

    def _get_cost_breakdowns(self, treatment_procedure: TreatmentProcedure):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            self.session.query(
                CostBreakdown
            )  # type: ignore[union-attr] # Item "None" of "Optional[Session]" has no attribute "query"
            .filter_by(treatment_procedure_uuid=treatment_procedure.uuid)
            .order_by(sa.desc(CostBreakdown.created_at))
            .all()
        )

    def _determine_tp_accumulation_status(
        self, treatment_procedure: TreatmentProcedure, bills: List[Bill]
    ) -> TreatmentAccumulationStatus:
        all_cost_breakdowns = self._get_cost_breakdowns(
            treatment_procedure=treatment_procedure
        )
        if not all_cost_breakdowns:
            log.error(
                f"No cost breakdown located for treatment procedure {treatment_procedure.uuid} with status "
                f"{treatment_procedure.status}"
            )
            return TreatmentAccumulationStatus.WAITING
        elif (
            treatment_procedure.status == TreatmentProcedureStatus.COMPLETED
            or treatment_procedure.status
            == TreatmentProcedureStatus.PARTIALLY_COMPLETED
        ) and all_cost_breakdowns[0].id == treatment_procedure.cost_breakdown_id:
            cost_breakdown = all_cost_breakdowns[0]
        else:
            log.error(
                "Cost breakdown data out of sync for treatment procedure "
                f"with status {treatment_procedure.status} and cost breakdown ID "
                f"{treatment_procedure.cost_breakdown_id}. Check if the cost breakdown ID on this treatment procedure"
                "is the most recent cost breakdown associated with it.",
                treatment_procedure_uuid=treatment_procedure.uuid,
            )
            return TreatmentAccumulationStatus.ROW_ERROR

        member_responsibility = cost_breakdown.total_member_responsibility
        if member_responsibility == 0:
            log.info(
                "Skipping accumulation for treatment procedure - no member "
                "responsibility",
                treatment_procedure_uuid=treatment_procedure.uuid,
            )
            return TreatmentAccumulationStatus.SKIP
        if sum([bill.amount for bill in bills]) >= member_responsibility:
            return TreatmentAccumulationStatus.PAID
        else:
            return TreatmentAccumulationStatus.WAITING

    def _insert_accumulation_treatment_mapping(
        self, accumulation_tp_mapping: Dict[str, ProcedureToAccumulationData]
    ) -> None:
        health_plan_repo = HealthPlanRepository(self.session)
        for tp_uuid, procedure_data in accumulation_tp_mapping.items():
            if not self._mapping_is_new(tp_uuid):
                log.warning(
                    "Skipping insert - Treatment procedure already present in mapping table",
                    treatment_procedure_uuid=tp_uuid,
                )
                continue

            if not self._mapping_is_this_payer(health_plan_repo, procedure_data):
                log.warning(
                    "Skipping insert - Treatment procedure associated with the wrong payer",
                    treatment_procedure_uuid=tp_uuid,
                )
                continue

            # If not already on the record & associated with the correct payer, insert the new mapping
            acc_trtmnt_mapping = AccumulationTreatmentMapping(
                treatment_procedure_uuid=tp_uuid,
                treatment_accumulation_status=procedure_data.status,
                completed_at=procedure_data.completed_date,
                payer_id=self.payer_id,
                is_refund=True
                if procedure_data.status == TreatmentAccumulationStatus.REFUNDED
                else False,
            )
            self.session.add(
                acc_trtmnt_mapping
            )  # type: ignore[union-attr] # Item "None" of "Optional[Session]" has no attribute "add"
            log.info(
                "Inserted treatment procedure into accumulation_treatment_mapping.",
                treatment_procedure_uuid=tp_uuid,
                status=procedure_data.status,
            )
            if get_flask_admin_user():
                emit_audit_log_create(acc_trtmnt_mapping)

    def _mapping_is_new(self, tp_uuid: str) -> bool:
        # We only want to insert treatment procedures not yet in the mapping table to avoid duplicates
        num_existing_mappings = (
            self.session.query(AccumulationTreatmentMapping)
            .filter(AccumulationTreatmentMapping.treatment_procedure_uuid == tp_uuid)
            .count()
        )
        return num_existing_mappings == 0

    def _mapping_is_this_payer(
        self,
        health_plan_repo: HealthPlanRepository,
        procedure_data: ProcedureToAccumulationData,
    ) -> bool:
        if not (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            == NEW_BEHAVIOR
        ):
            # If year-over-year health plans are not enabled, do not do this test.
            return True
        # Now that health plans are per-time period,
        # it's possible for a wallet to appear in multiple data sourcing runs
        # We only want to insert procedures associated with the right payer per-sourcing run.
        # TODO: get rid of per-payer sourcing runs
        employer_health_plan = (
            health_plan_repo.get_employer_plan_by_wallet_and_member_id(
                wallet_id=procedure_data.wallet_id,
                member_id=procedure_data.member_id,
                effective_date=procedure_data.start_date,
            )
        )
        return bool(
            employer_health_plan
            and employer_health_plan.benefits_payer_id == self.payer_id
        )

    def _update_accumulation_treatment_mapping(
        self, accumulation_tp_mapping: Dict[str, ProcedureToAccumulationData]
    ) -> None:
        for tp_uuid, procedure_data in accumulation_tp_mapping.items():
            self.session.query(AccumulationTreatmentMapping).filter(
                # type: ignore[union-attr] # Item "None" of "Optional[Session]" has no attribute "query"
                sa.and_(
                    AccumulationTreatmentMapping.payer_id == self.payer_id,
                    AccumulationTreatmentMapping.treatment_procedure_uuid == tp_uuid,
                )
            ).update({"treatment_accumulation_status": procedure_data.status})
            log.info(
                "Updated treatment procedure.",
                treatment_procedure_uuid=tp_uuid,
                status=procedure_data.status,
            )
        self.session.commit()  # type: ignore[union-attr] # Item "None" of "Optional[Session]" has no attribute "commit"
