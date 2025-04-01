from __future__ import annotations

import datetime
from typing import List, Optional

import sqlalchemy
from maven import feature_flags
from sqlalchemy import func, or_

from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from models.enterprise import Organization
from models.profiles import Address
from payer_accumulator import helper_functions
from payer_accumulator.common import (
    OrganizationName,
    PayerName,
    TreatmentAccumulationStatus,
)
from payer_accumulator.errors import (
    NoCostBreakdownError,
    NoHealthPlanFoundError,
    NoMappingDataProvidedError,
    NoOrganizationFoundError,
)
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
    PayerReportStatus,
)
from storage import connection
from utils.log import logger
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlan,
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import MemberHealthPlan, ReimbursementWallet
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    OLD_BEHAVIOR,
    HealthPlanRepository,
)

log = logger(__name__)


class AccumulationFileGeneratorMixin:
    def __init__(
        self,
        payer_name: PayerName,
        session: Optional[sqlalchemy.orm.Session] = None,
        organization_name: Optional[OrganizationName] = None,
        health_plan_name: Optional[str] = None,
    ):
        self.session = session or connection.db.session
        self.payer_name: PayerName = payer_name
        self.organization_name = organization_name
        self.health_plan_name = health_plan_name
        self.payer_id: int = helper_functions.get_payer_id(
            payer_name=payer_name, log=log
        )
        self.health_plan_repo = HealthPlanRepository(session=self.session)
        self.run_time = datetime.datetime.utcnow()

    def get_cost_breakdown(
        self,
        treatment_procedure: Optional[TreatmentProcedure] = None,
        reimbursement_request: Optional[ReimbursementRequest] = None,
    ) -> CostBreakdown:
        if treatment_procedure is not None:
            cost_breakdown = (
                self.session.query(CostBreakdown)
                .filter(CostBreakdown.id == treatment_procedure.cost_breakdown_id)
                .one_or_none()
            )
        elif reimbursement_request is not None:
            cost_breakdown = (
                self.session.query(CostBreakdown)
                .filter(
                    CostBreakdown.reimbursement_request_id == reimbursement_request.id
                )
                .order_by(CostBreakdown.created_at.desc())
                .first()
            )
        else:
            raise NoMappingDataProvidedError(
                "No treatment procedure or reimbursement request provided"
            )
        if not cost_breakdown:
            log.error(
                "Cost breakdown is missing for accumulation mapping.",
                treatment_procedure_uuid=(
                    treatment_procedure.uuid if treatment_procedure else None
                ),
                reimbursement_request_id=(
                    str(reimbursement_request.id) if reimbursement_request else None
                ),
            )
            raise NoCostBreakdownError("No cost breakdown")
        return cost_breakdown

    def create_new_accumulation_report(
        self,
        payer_id: int,
        file_name: str,
        run_time: datetime.datetime,
    ) -> PayerAccumulationReports:
        report = PayerAccumulationReports(
            payer_id=payer_id,
            filename=file_name,
            report_date=run_time.strftime("%Y-%m-%d"),
            status=PayerReportStatus.NEW,
        )
        self.session.add(report)
        # flush is needed to generate report.id
        self.session.flush()
        return report

    def get_accumulation_mappings_with_data(
        self,
        payer_id: int,
        organization_id: Optional[int] = None,
        health_plan_ids: Optional[List[int]] = None,
    ) -> list:
        log.info(
            "Getting accumulation mappings",
            payer_id=payer_id,
            organization_id=organization_id,
            health_plan_id=health_plan_ids,
        )
        query = self.accumulation_mapping_query_builder(
            payer_id, organization_id, health_plan_ids
        )
        mappings = query.order_by(AccumulationTreatmentMapping.created_at).all()
        log.info("Found mappings", count=len(mappings))
        return mappings

    def accumulation_mapping_query_builder(
        self,
        payer_id: int,
        organization_id: Optional[int],
        health_plan_ids: Optional[List[int]],
    ) -> sqlalchemy.orm.Query:
        # Base query with common joins
        query = (
            self.session.query(
                AccumulationTreatmentMapping, TreatmentProcedure, ReimbursementRequest
            )
            .outerjoin(
                TreatmentProcedure,
                AccumulationTreatmentMapping.treatment_procedure_uuid
                == TreatmentProcedure.uuid,
            )
            .outerjoin(
                ReimbursementRequest,
                AccumulationTreatmentMapping.reimbursement_request_id
                == ReimbursementRequest.id,
            )
        )

        # Conditionally add joins and filters based on organization_id
        if organization_id is not None:
            query = (
                query.outerjoin(
                    ReimbursementWallet,
                    or_(
                        TreatmentProcedure.reimbursement_wallet_id
                        == ReimbursementWallet.id,
                        ReimbursementRequest.reimbursement_wallet_id
                        == ReimbursementWallet.id,
                    ),
                )
                .outerjoin(
                    ReimbursementOrganizationSettings,
                    ReimbursementWallet.reimbursement_organization_settings_id
                    == ReimbursementOrganizationSettings.id,
                )
                .filter(
                    ReimbursementOrganizationSettings.organization_id == organization_id
                )
            )
        # Conditionally add joins and filters based on health_plan_id if organization_id is not provided
        elif health_plan_ids is not None:
            query = (
                query.outerjoin(
                    ReimbursementWallet,
                    or_(
                        TreatmentProcedure.reimbursement_wallet_id
                        == ReimbursementWallet.id,
                        ReimbursementRequest.reimbursement_wallet_id
                        == ReimbursementWallet.id,
                    ),
                )
                .outerjoin(
                    MemberHealthPlan,
                    MemberHealthPlan.reimbursement_wallet_id == ReimbursementWallet.id,
                )
                .filter(MemberHealthPlan.employer_health_plan_id.in_(health_plan_ids))
            )

        # Add common filters
        query = query.filter(
            AccumulationTreatmentMapping.treatment_accumulation_status.in_(
                [
                    TreatmentAccumulationStatus.PAID,
                    TreatmentAccumulationStatus.REFUNDED,
                ]
            ),
            AccumulationTreatmentMapping.payer_id == payer_id,
        )
        return query

    def get_member_health_plan(
        self,
        member_id: int,
        wallet_id: int,
        effective_date: datetime.datetime | datetime.date | None,
    ) -> Optional[MemberHealthPlan]:
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != OLD_BEHAVIOR
        ):
            member_health_plan = (
                self.health_plan_repo.get_member_plan_by_wallet_and_member_id(
                    member_id=member_id,
                    wallet_id=wallet_id,
                    effective_date=effective_date,
                )
            )
        else:
            member_health_plan = (
                self.session.query(MemberHealthPlan)
                .filter(MemberHealthPlan.member_id == member_id)
                .filter(MemberHealthPlan.reimbursement_wallet_id == wallet_id)
                .one_or_none()
            )
        return member_health_plan

    def get_member_address(self, member_id: int) -> Optional[Address]:
        return (
            self.session.query(Address)
            .filter(Address.user_id == member_id)
            .one_or_none()
        )

    def _get_organization_id(self, organization_name: str) -> int:
        client_name = organization_name.replace("_", " ").lower()
        org_id = (
            self.session.query(Organization.id)
            .distinct()
            .filter(func.lower(Organization.name).like(client_name))
            .first()
        )
        if org_id is None:
            log.error(
                "Cannot find org id for the organization provided",
                organization_name=self.organization_name,
            )
            raise NoOrganizationFoundError(
                f"No organization found for {organization_name}"
            )
        else:
            return org_id[0]

    def _get_health_plan_ids(self, health_plan_name: str) -> List[int]:
        log.info(
            "Searching for health plan",
            health_plan_name=health_plan_name,
        )
        health_plan_results = (
            self.session.query(EmployerHealthPlan.id, EmployerHealthPlan.name)
            .distinct()
            .filter(EmployerHealthPlan.benefits_payer_id == self.payer_id)
            .filter(func.lower(EmployerHealthPlan.name).like(f"%{health_plan_name}%"))
            .all()
        )
        health_plan_ids = [
            health_plan_result[0] for health_plan_result in health_plan_results
        ]
        if not health_plan_ids:
            log.error(
                "Cannot find employer health plan id for the health plan provided",
                health_plan_name=self.health_plan_name,
            )
            raise NoHealthPlanFoundError(
                f"No health plans found for {health_plan_name}"
            )
        log.info(
            "Found health plans",
            health_plan_id=health_plan_ids,
            health_plan_names=[
                health_plan_result[1] for health_plan_result in health_plan_results
            ],
        )
        return health_plan_ids
