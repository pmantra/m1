import dataclasses
import datetime
from collections import defaultdict
from typing import List, Optional, Tuple

from maven import feature_flags
from sqlalchemy.sql import and_, or_

from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.file_generators.fixed_width_accumulation_file_generator import (
    FixedWidthAccumulationFileGenerator,
)
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
)
from storage.connection import db
from storage.connector import RoutingSQLAlchemy
from utils.log import logger
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    NEW_BEHAVIOR,
    OLD_BEHAVIOR,
)

log = logger(__name__)


@dataclasses.dataclass
class AccumulatorAppliedData:
    cardholder_id: str = ""
    date_of_birth: Optional[datetime.date] = None
    deductible: int = 0
    oop_applied: int = 0


MemberSumsT = defaultdict[str, AccumulatorAppliedData]
DbSumDataT = List[Tuple[AccumulationTreatmentMapping, MemberHealthPlan]]


class AccumulationReportValidator:
    __slots__ = ("valid_mapping_statuses", "session")

    def __init__(self, session: Optional[RoutingSQLAlchemy] = None):
        self.valid_mapping_statuses: List[TreatmentAccumulationStatus] = [
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.SUBMITTED,
            TreatmentAccumulationStatus.ACCEPTED,
        ]
        self.session = session or db.session

    def validate_report_member_sums(
        self,
        report: PayerAccumulationReports,
        raw_report: str,
        file_generator: FixedWidthAccumulationFileGenerator,
    ) -> None:
        """
        Log any missing or mismatched accumulations between AccumulationTreatmentMappings for a PayerAccumulationReports
        and the raw report data to enable validation and audit of accumulation submissions to payers.

        report: The PayerAccumulationReports DB object that this validation is running on.
        raw_report: The raw report data that this validation is running on.
        file_generator: The AccumulationFileGenerator associated with this report's payer
        """
        report_content_sums = self.get_member_sums_from_raw_report(
            raw_report=raw_report, file_generator=file_generator, report_id=report.id
        )
        db_content_sums = self.get_member_sums_from_db(
            report_id=report.id, file_generator=file_generator
        )

        # Compare subscriber id + date strings for all rows
        in_report_not_in_db = set(report_content_sums.keys()).difference(
            set(db_content_sums.keys())
        )
        if in_report_not_in_db:
            for member_sum_key in in_report_not_in_db:
                data = report_content_sums[member_sum_key]
                wallet_ids = self._get_wallet_ids_as_str_by_subscriber_info(
                    subscriber_id=data.cardholder_id,
                    date_of_birth=data.date_of_birth,
                    payer_id=report.payer_id,
                    report_id=report.id,
                )
                log.error(
                    "Mismatched Payer Accumulation Data",
                    error_detail="Data in the report, but not in the db.",
                    wallet_ids=wallet_ids,
                    report_id=str(report.id),
                )

        in_db_not_in_report = set(db_content_sums.keys()).difference(
            set(report_content_sums.keys())
        )
        if in_db_not_in_report:
            for member_sum_key in in_db_not_in_report:
                data = db_content_sums[member_sum_key]
                wallet_ids = self._get_wallet_ids_as_str_by_subscriber_info(
                    subscriber_id=data.cardholder_id,
                    date_of_birth=data.date_of_birth,
                    payer_id=report.payer_id,
                    report_id=report.id,
                )
                log.error(
                    "Mismatched Payer Accumulation Data",
                    error_detail="Data in the db, but not in the report.",
                    wallet_ids=wallet_ids,
                    report_id=str(report.id),
                )

        # Compare values for keys present in both sets of sums
        shared_keys = set(report_content_sums.keys()).intersection(
            set(db_content_sums.keys())
        )
        for member_sum_key in shared_keys:
            report_data = report_content_sums[member_sum_key]
            db_data = db_content_sums[member_sum_key]
            if (
                db_data.deductible != report_data.deductible
                or db_data.oop_applied != report_data.oop_applied
            ):
                wallet_ids = self._get_wallet_ids_as_str_by_subscriber_info(
                    subscriber_id=report_data.cardholder_id,
                    date_of_birth=report_data.date_of_birth,
                    payer_id=report.payer_id,
                    report_id=report.id,
                )
                log.error(
                    "Mismatched Payer Accumulation Data",
                    error_detail="Data in the db and data in the report do not match.",
                    wallet_ids=wallet_ids,
                    report_id=str(report.id),
                    report_deductible_sum=report_data.deductible,
                    db_deductible_sum=db_data.deductible,
                    report_oop_sum=report_data.oop_applied,
                    db_oop_sum=db_data.oop_applied,
                )

    def get_member_sums_from_raw_report(
        self,
        file_generator: FixedWidthAccumulationFileGenerator,
        raw_report: str,
        report_id: int,
    ) -> MemberSumsT:
        """
        Sum all deductible and oop accumulations based on the raw report file.
        """
        structured_data = file_generator.file_contents_to_dicts(raw_report)
        detail_rows = file_generator.get_detail_rows(structured_data)

        member_sums = defaultdict(AccumulatorAppliedData)  # type: ignore[arg-type] # error: Argument 1 to "defaultdict" has incompatible type "type[AccumulatorAppliedData]"; expected "Callable[[], Never] | None"
        for detail_row in detail_rows:
            cardholder_id = file_generator.get_cardholder_id_from_detail_dict(
                detail_row_dict=detail_row
            )
            if not cardholder_id:
                log.error(
                    "Could not pull a cardholder id from a report detail for report validation.",
                    report_id=str(report_id),
                )
                cardholder_id = ""
            # TODO: make this date into a datetime (Not urgent, only used in a sql query where it's transformed anyway)
            date_of_birth = file_generator.get_dob_from_report_row(
                detail_row_dict=detail_row
            )

            deductible = file_generator.get_deductible_from_row(detail_row=detail_row)
            oop = file_generator.get_oop_from_row(detail_row=detail_row)

            member_sums_key = self._get_db_member_sums_key(
                date_of_birth=date_of_birth, subscriber_id=cardholder_id
            )
            member_sums[member_sums_key].deductible += deductible
            member_sums[member_sums_key].oop_applied += oop
            member_sums[member_sums_key].date_of_birth = date_of_birth
            member_sums[member_sums_key].cardholder_id = cardholder_id
        return member_sums

    def get_member_sums_from_db(
        self, report_id: int, file_generator: FixedWidthAccumulationFileGenerator
    ) -> MemberSumsT:
        """
        Sum all deductible and oop accumulations based on the database data.
        """
        tp_mappings = self._get_treatment_procedures_mappings(report_id=report_id)
        rr_mappings = self._get_reimbursement_requests_mappings(report_id=report_id)
        mappings = tp_mappings + rr_mappings

        member_sums = defaultdict(AccumulatorAppliedData)  # type: ignore[arg-type] # error: Argument 1 to "defaultdict" has incompatible type "type[AccumulatorAppliedData]"; expected "Callable[[], Never] | None"
        for mapping, member_health_plan in mappings:
            cardholder_id = file_generator.get_cardholder_id(
                member_health_plan=member_health_plan
            )
            date_of_birth = member_health_plan.patient_date_of_birth
            deductible = mapping.deductible
            oop_applied = mapping.oop_applied

            member_sums_key = self._get_db_member_sums_key(
                date_of_birth=date_of_birth,
                subscriber_id=cardholder_id,
            )
            member_sums[member_sums_key].deductible += deductible
            member_sums[member_sums_key].oop_applied += oop_applied
            member_sums[member_sums_key].date_of_birth = date_of_birth
            member_sums[member_sums_key].cardholder_id = cardholder_id
        return member_sums

    def _get_reimbursement_requests_mappings(self, report_id: int) -> DbSumDataT:
        """
        Returns all AccumulationTreatmentMappings for relevant reimbursement requests
        """
        base_query = self.session.query(
            AccumulationTreatmentMapping, MemberHealthPlan
        ).join(
            ReimbursementRequest,
            ReimbursementRequest.id
            == AccumulationTreatmentMapping.reimbursement_request_id,
        )

        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            == NEW_BEHAVIOR
        ):
            base_query = base_query.join(
                MemberHealthPlan,
                and_(
                    ReimbursementRequest.person_receiving_service_id
                    == MemberHealthPlan.member_id,
                    MemberHealthPlan.reimbursement_wallet_id
                    == ReimbursementRequest.reimbursement_wallet_id,
                    ReimbursementRequest.service_start_date
                    >= MemberHealthPlan.plan_start_at,
                    or_(
                        ReimbursementRequest.service_start_date
                        <= MemberHealthPlan.plan_end_at,
                        MemberHealthPlan.plan_end_at.is_(None),
                    ),
                ),
            )
        else:
            base_query = base_query.join(
                MemberHealthPlan,
                MemberHealthPlan.reimbursement_wallet_id
                == ReimbursementRequest.reimbursement_wallet_id,
            )
            # NOTE: cannot log intermediate rollout effective date here without adding a second query

        return (
            base_query.filter(
                AccumulationTreatmentMapping.report_id == report_id,
                AccumulationTreatmentMapping.treatment_accumulation_status.in_(
                    self.valid_mapping_statuses
                ),
            )
            .group_by(AccumulationTreatmentMapping.id)
            .all()
        )

    def _get_treatment_procedures_mappings(self, report_id: int) -> DbSumDataT:
        """
        Returns all AccumulationTreatmentMappings for relevant treatment procedures
        """
        base_query = self.session.query(
            AccumulationTreatmentMapping, MemberHealthPlan
        ).join(
            TreatmentProcedure,
            TreatmentProcedure.uuid
            == AccumulationTreatmentMapping.treatment_procedure_uuid,
        )
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            == NEW_BEHAVIOR
        ):
            # Comparing dates to datetimes here -- will need test cases.
            base_query = base_query.join(
                MemberHealthPlan,
                and_(
                    TreatmentProcedure.member_id == MemberHealthPlan.member_id,
                    MemberHealthPlan.reimbursement_wallet_id
                    == TreatmentProcedure.reimbursement_wallet_id,
                    TreatmentProcedure.start_date >= MemberHealthPlan.plan_start_at,
                    or_(
                        TreatmentProcedure.start_date <= MemberHealthPlan.plan_end_at,
                        MemberHealthPlan.plan_end_at.is_(None),
                    ),
                ),
            )
        else:
            base_query = base_query.join(
                MemberHealthPlan,
                MemberHealthPlan.reimbursement_wallet_id
                == TreatmentProcedure.reimbursement_wallet_id,
            )
            # NOTE: cannot log intermediate rollout effective date here without adding a second query

        return (
            base_query.filter(
                AccumulationTreatmentMapping.report_id == report_id,
                AccumulationTreatmentMapping.treatment_accumulation_status.in_(
                    self.valid_mapping_statuses
                ),
            )
            .group_by(AccumulationTreatmentMapping.id)
            .all()
        )

    def _get_db_member_sums_key(
        self, date_of_birth: Optional[datetime.date], subscriber_id: str
    ) -> str:
        # Note: the subscriber_id here must be pulled using the file_generator
        # as different health plan providers trim the id in different ways.
        if not date_of_birth:
            return subscriber_id.upper()

        # it is possible for two users to have the same cardholder id and date of birth,
        # in which case, we will have an interesting problem here.
        key = date_of_birth.strftime("%Y%m%d") + subscriber_id

        # make case-insensitive due to PAY-5840
        return key.upper()

    def _get_wallet_ids_as_str_by_subscriber_info(
        self,
        subscriber_id: Optional[str],
        date_of_birth: Optional[datetime.date],
        payer_id: int,
        report_id: int,
    ) -> List[str]:
        if not subscriber_id or not date_of_birth:
            log.error(
                "No wallet identified for accumulation validation.",
                error_detail="Wallet identification data not provided.",
                payer_id=str(payer_id),
                report_id=str(report_id),
            )
            return []
        wallet_ids = (
            self.session.query(MemberHealthPlan)
            .with_entities(MemberHealthPlan.reimbursement_wallet_id)
            .join(
                EmployerHealthPlan,
                EmployerHealthPlan.id == MemberHealthPlan.employer_health_plan_id,
            )
            .filter(
                MemberHealthPlan.subscriber_insurance_id.contains(subscriber_id),
                MemberHealthPlan.patient_date_of_birth == date_of_birth,
                EmployerHealthPlan.benefits_payer_id == payer_id,
            )
            .distinct()
            .all()
        )
        if not wallet_ids:
            log.error(
                "No wallet identified for accumulation validation.",
                error_detail="No wallet returned for identifying data.",
                payer_id=str(payer_id),
                report_id=str(report_id),
            )
            return []
        elif len(wallet_ids) > 1:
            log.error(
                "Numerous potential wallets found for accumulation validation.",
                wallet_ids=[str(wallet[0]) for wallet in wallet_ids],
                payer_id=str(payer_id),
                report_id=str(report_id),
            )
        return [str(wallet_id[0]) for wallet_id in wallet_ids]
