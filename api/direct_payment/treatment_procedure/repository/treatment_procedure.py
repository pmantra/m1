from __future__ import annotations

import datetime
from traceback import format_exc
from typing import Optional, Union

import ddtrace.ext
import sqlalchemy.orm.scoping
from flask_restful import abort

from common import stats
from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.clinic.models.fee_schedule import FeeScheduleGlobalProcedures
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.repository.treatment_procedures_needing_questionnaires_repository import (
    TreatmentProceduresNeedingQuestionnairesRepository,
)
from storage import connection
from storage.connector import RoutingSession
from utils.log import logger
from wallet.models.constants import BenefitTypes, PatientInfertilityDiagnosis
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)
metric_prefix = "api.direct_payment.treatment_procedure.repository.treatment_procedure"


class TreatmentProcedureRepository:
    def __init__(self, session: Union[sqlalchemy.orm.scoping.ScopedSession, RoutingSession, None] = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.session = session or connection.db.session

    @trace_wrapper
    def read(self, *, treatment_procedure_id: int) -> TreatmentProcedure | None:
        treatment_procedure = self.session.query(TreatmentProcedure).get(
            treatment_procedure_id
        )
        if not treatment_procedure:
            stats.increment(
                metric_name=f"{metric_prefix}.read",
                pod_name=stats.PodNames.BENEFITS_EXP,
                tags=["error:true"],
            )
            abort(404, message="Treatment Procedure not found")
        return treatment_procedure

    @trace_wrapper
    def create(
        self,
        *,
        member_id: int,
        infertility_diagnosis: Optional[PatientInfertilityDiagnosis] = None,
        reimbursement_wallet_id: int,
        reimbursement_request_category_id: int,
        fee_schedule_id: int,
        global_procedure_id: str,
        global_procedure_name: str,
        global_procedure_credits: int,
        fertility_clinic_id: int,
        fertility_clinic_location_id: int,
        start_date: datetime.date,
        end_date: Optional[datetime.date] = None,
        completed_date: Optional[datetime.date] = None,
        status: Optional[TreatmentProcedureStatus] = TreatmentProcedureStatus.SCHEDULED,
        global_procedure_type: Optional[
            TreatmentProcedureType
        ] = TreatmentProcedureType.MEDICAL,
    ) -> TreatmentProcedure:
        """
        Creates and returns a TreatmentProcedure. Commits to the DB.
        """
        wallet = ReimbursementWallet.query.get(reimbursement_wallet_id)
        reimbursement_category = wallet.get_direct_payment_category
        if not reimbursement_category:
            log.warning(
                "ReimbursementCategory not found for new procedure.",
                wallet_id=wallet.id,
            )
            abort(
                400,
                message="Could not find direct payment reimbursement category for wallet",
            )
        if reimbursement_category.id != reimbursement_request_category_id:
            log.warning(
                "Direct payment category in wallet found does not match with given reimbursement_request_category_id",
                wallet_reimbursement_category_id=reimbursement_category.id,
                reimbursement_request_category_id=reimbursement_request_category_id,
            )
            abort(
                400,
                message="Direct payment category in wallet found does not match with given reimbursement_request_category_id",
            )

        benefit_type = wallet.category_benefit_type(
            request_category_id=reimbursement_category.id
        )

        fee_schedule_gp = FeeScheduleGlobalProcedures.query.filter(
            FeeScheduleGlobalProcedures.global_procedure_id == global_procedure_id,
            FeeScheduleGlobalProcedures.fee_schedule_id == fee_schedule_id,
        ).one_or_none()
        if not fee_schedule_gp:
            log.warning(
                "FeeScheduleGlobalProcedures not found for new procedure.",
                global_procedure_id=global_procedure_id,
                fee_schedule_id=fee_schedule_id,
            )
            abort(400, message="FeeScheduleGlobalProcedures not found for procedure.")
        cost = fee_schedule_gp.cost
        cost_credit = None
        if benefit_type == BenefitTypes.CYCLE:
            cost_credit = global_procedure_credits
            if not cost_credit:
                log.warning(
                    "Global procedure credits are none",
                    global_procedure_id=global_procedure_id,
                    wallet_id=wallet.id,
                    member_id=member_id,
                )

        treatment_procedure = TreatmentProcedure(
            member_id=member_id,
            infertility_diagnosis=infertility_diagnosis,
            reimbursement_wallet_id=reimbursement_wallet_id,
            reimbursement_request_category_id=reimbursement_request_category_id,
            fee_schedule_id=fee_schedule_id,
            global_procedure_id=global_procedure_id,
            fertility_clinic_id=fertility_clinic_id,
            fertility_clinic_location_id=fertility_clinic_location_id,
            start_date=start_date,
            end_date=end_date,
            completed_date=completed_date,
            procedure_name=global_procedure_name,
            cost=cost,
            cost_credit=cost_credit,
            status=status,
            procedure_type=global_procedure_type,
        )

        try:
            self.session.add(treatment_procedure)
            self.session.flush()
            TreatmentProceduresNeedingQuestionnairesRepository(
                self.session
            ).create_tpnq_from_treatment_procedure_id(
                treatment_procedure_id=treatment_procedure.id
            )
            self.session.commit()
        except Exception as e:
            log.error(
                "Failed to create treatment procedure record",
                error=str(e),
                traceback=format_exc(),
            )
            stats.increment(
                metric_name=f"{metric_prefix}.create",
                pod_name=stats.PodNames.BENEFITS_EXP,
                tags=["error:true"],
            )
            abort(400, message="Error creating treatment procedure record", error=e)

        return treatment_procedure

    @trace_wrapper
    def get_all_treatments_from_wallet_id(
        self, wallet_id: int
    ) -> list[TreatmentProcedure]:
        """
        Returns all treatment_procedures affiliated with a given wallet_id, sorted
        by (treatment_procedure.start_date, treatment_procedure.created_at) asc.
        """
        return (
            self.session.query(TreatmentProcedure)
            .filter(
                TreatmentProcedure.reimbursement_wallet_id == wallet_id,
            )
            .order_by(
                TreatmentProcedure.start_date.asc(), TreatmentProcedure.created_at.asc()
            )
            .all()
        )

    @trace_wrapper
    def get_treatments_by_uuids(
        self, treatment_procedure_uuids: list[str]
    ) -> list[TreatmentProcedure]:
        return (
            self.session.query(TreatmentProcedure)
            .filter(TreatmentProcedure.uuid.in_(treatment_procedure_uuids))
            .all()
        )

    @trace_wrapper
    def get_treatments_by_ids(
        self, treatment_procedure_ids: list[int]
    ) -> list[TreatmentProcedure]:
        return (
            self.session.query(TreatmentProcedure)
            .filter(TreatmentProcedure.id.in_(treatment_procedure_ids))
            .all()
        )

    @trace_wrapper
    def get_scheduled_procedures_and_cbs(
        self, wallet_id: int, category_id: int
    ) -> list[tuple[TreatmentProcedure, Optional[CostBreakdown]]]:
        query = (
            self.session.query(TreatmentProcedure, CostBreakdown)
            .outerjoin(
                CostBreakdown,
                TreatmentProcedure.cost_breakdown_id == CostBreakdown.id,
            )
            .filter(
                TreatmentProcedure.reimbursement_wallet_id == wallet_id,
                TreatmentProcedure.reimbursement_request_category_id == category_id,
                TreatmentProcedure.status == TreatmentProcedureStatus.SCHEDULED,
            )
        )
        return query.all()

    @trace_wrapper
    def get_treatments_since_datetime_from_statuses_type_wallet_ids(
        self,
        wallet_ids: list[int],
        statuses: list[TreatmentProcedureStatus],
        procedure_type: TreatmentProcedureType | None = None,
        cutoff: datetime | None = None,  # type: ignore[valid-type] # Module "datetime" is not valid as a type
        member_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "member_id" (default has type "None", argument has type "int")
    ) -> list[TreatmentProcedure]:
        """
        Returns all treatment_procedures affiliated with given wallet_ids and statuses since datetime cutoff.
        """
        sql_where = sqlalchemy.and_(
            TreatmentProcedure.reimbursement_wallet_id.in_(wallet_ids),
            TreatmentProcedure.status.in_(statuses),
        )
        if procedure_type:
            sql_where = sqlalchemy.and_(
                sql_where, TreatmentProcedure.procedure_type == procedure_type
            )
        if cutoff:
            sql_where = sqlalchemy.and_(
                sql_where, TreatmentProcedure.completed_date >= cutoff
            )
        if member_id:
            sql_where = sqlalchemy.and_(
                sql_where, TreatmentProcedure.member_id == member_id
            )
        return self.session.query(TreatmentProcedure).filter(sql_where).all()

    @trace_wrapper
    def get_treatment_procedures_with_statuses_since_datetime(
        self,
        statuses: list[str],
        cutoff: datetime.datetime,
    ) -> list[TreatmentProcedure]:
        """
        Returns all treatment_procedures with status since datetime cutoff.
        """
        enum_statuses = [TreatmentProcedureStatus(status) for status in statuses]
        sql_where = sqlalchemy.and_(
            TreatmentProcedure.status.in_(enum_statuses),
            TreatmentProcedure.created_at >= cutoff,
        )
        return self.session.query(TreatmentProcedure).filter(sql_where).all()

    @trace_wrapper
    def get_wallet_payment_history_procedures(
        self, wallet_id: int, ids: list[int]
    ) -> list[TreatmentProcedure]:
        """
        Return all requested procedures and all upcoming procedures.
        """
        treatment_procedures = (
            self.session.query(TreatmentProcedure)
            .filter(
                sqlalchemy.and_(
                    sqlalchemy.or_(
                        TreatmentProcedure.id.in_(ids),
                        TreatmentProcedure.status == TreatmentProcedureStatus.SCHEDULED,
                    ),
                    TreatmentProcedure.reimbursement_wallet_id == wallet_id,
                )
            )
            .all()
        )
        return treatment_procedures

    @trace_wrapper
    def update(
        self,
        *,
        treatment_procedure_id: int,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        status: Optional[TreatmentProcedureStatus] = None,
        partial_procedure_id: Optional[int] = None,
    ) -> TreatmentProcedure:
        treatment_procedure = self.read(treatment_procedure_id=treatment_procedure_id)
        if status == TreatmentProcedureStatus.CANCELLED:
            treatment_procedure.cancelled_date = end_date
            treatment_procedure.end_date = end_date
        elif (
            status == TreatmentProcedureStatus.COMPLETED
            or status == TreatmentProcedureStatus.PARTIALLY_COMPLETED
        ):
            treatment_procedure.completed_date = datetime.datetime.now(
                tz=datetime.timezone.utc
            )
            treatment_procedure.end_date = end_date

        if start_date:
            treatment_procedure.start_date = start_date
        if end_date:
            treatment_procedure.end_date = end_date
        if status:
            treatment_procedure.status = status
        if partial_procedure_id:
            treatment_procedure.partial_procedure_id = partial_procedure_id

        try:
            self.session.add(treatment_procedure)
            self.session.commit()
        except Exception as e:
            log.error(
                "Failed to update treatment procedure record",
                error=str(e),
                traceback=format_exc(),
            )
            stats.increment(
                metric_name=f"{metric_prefix}.update",
                pod_name=stats.PodNames.BENEFITS_EXP,
                tags=["error:true"],
            )
            abort(400, message="Error updating treatment procedure record", error=e)

        return treatment_procedure
