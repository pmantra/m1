from __future__ import annotations

import datetime
from typing import Tuple

from sqlalchemy import or_

from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.billing import models as billing_models
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.constants import MEMBER_BILLING_OFFSET_DAYS
from direct_payment.clinic.repository.clinic_location import (
    FertilityClinicLocationRepository,
)
from direct_payment.payments.constants import DetailLabel
from direct_payment.payments.models import (
    CostResponsibilityT,
    DisplayDatesT,
    PaymentDetail,
    PaymentDetailBreakdown,
    PaymentRecord,
    PaymentRecordForReimbursementWallet,
    PaymentStatusT,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from utils.log import logger
from wallet.models.constants import BenefitTypes
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.repository.reimbursement_request import ReimbursementRequestRepository

log = logger(__name__)


class PaymentsHelper:
    def __init__(self, session):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.billing_service = BillingService(session=session)
        self.treatment_procedure_repo = TreatmentProcedureRepository(session)
        self.clinic_loc_repo = FertilityClinicLocationRepository(session=session)

    def return_historic_records(
        self,
        bills: list[billing_models.Bill],
        procedure_map: dict,
        cost_breakdown_map: dict,
        allow_voided_payment_status: bool = False,
    ) -> list[PaymentRecord]:
        historic_bills = filter(
            lambda bill: bill.status in billing_models.HISTORIC_STATUS, bills
        )
        historic_records = self.create_payment_records(
            historic_bills,
            procedure_map,
            cost_breakdown_map,
            allow_voided_payment_status,
        )
        # Apply display order as per Member Payments functional requirement 3.8.
        historic_records = sorted(
            historic_records, key=lambda record: record.completed_at, reverse=True
        )
        return historic_records

    def return_upcoming_records_for_reimbursement_wallet(
        self,
        bills: list[billing_models.Bill],
        bill_procedure_ids: frozenset,
        procedure_map: dict,
        cost_breakdown_map: dict,
    ) -> list[PaymentRecordForReimbursementWallet]:
        # Build pending procedure and bill records, then combine them.
        pending_procedure_ids = procedure_map.keys() - bill_procedure_ids
        pending_records = self.create_pending_payment_records_for_reimbursement_wallet(
            pending_procedure_ids, procedure_map
        )
        upcoming_bills = [
            bill for bill in bills if bill.status in billing_models.UPCOMING_STATUS
        ]

        upcoming_records = (
            self.create_upcoming_payment_records_for_reimbursement_wallet(
                upcoming_bills, procedure_map, cost_breakdown_map
            )
        )

        # Apply display order as per Member Payments functional requirement 3.8.
        all_upcoming_records = sorted(
            upcoming_records + pending_records,
            key=lambda record: (  # type: ignore[arg-type] # Argument "key" to "sorted" has incompatible type "Callable[[PaymentRecordForReimbursementWallet], Optional[datetime]]"; expected "Callable[[PaymentRecordForReimbursementWallet], Union[SupportsDunderLT[Any], SupportsDunderGT[Any]]]"
                record.created_at  # type: ignore[return-value] # Incompatible return value type (got "Optional[datetime]", expected "Union[SupportsDunderLT[Any], SupportsDunderGT[Any]]")
                if record.payment_status == "PENDING" or record.due_at is None
                else record.due_at
            ),
        )
        # Always display failed bills first.
        all_upcoming_records.sort(
            key=lambda record: (
                0
                if record.payment_status == billing_models.BillStatus.FAILED.value
                else 1
            ),
        )
        return all_upcoming_records

    def return_upcoming_records(
        self,
        bills: list[billing_models.Bill],
        bill_procedure_ids: set,
        procedure_map: dict,
        cost_breakdown_map: dict,
        allow_voided_payment_status: bool = False,
    ) -> list[PaymentRecord]:
        # build pending procedure and bill records, then combine them.
        pending_procedure_ids = procedure_map.keys() - bill_procedure_ids
        pending_procedure_ids = self._procedures_without_estimates(
            list(pending_procedure_ids)
        )
        pending_records = self.create_pending_payment_records(
            pending_procedure_ids, procedure_map
        )
        upcoming_bills = filter(
            lambda bill: bill.status in billing_models.UPCOMING_STATUS, bills
        )
        upcoming_records = self.create_payment_records(
            upcoming_bills,
            procedure_map,
            cost_breakdown_map,
            allow_voided_payment_status,
        )

        # Apply display order as per Member Payments functional requirement 3.8.
        all_upcoming_records = sorted(
            upcoming_records + pending_records,
            key=lambda record: (
                record.created_at
                if record.payment_status == "PENDING" or record.due_at is None
                else record.due_at
            ),
        )
        # Always display failed bills first.
        all_upcoming_records = sorted(
            all_upcoming_records,
            key=lambda record: (
                0
                if record.payment_status == billing_models.BillStatus.FAILED.value
                else 1
            ),
        )
        return all_upcoming_records

    def _procedures_without_estimates(self, procedure_ids: list) -> set:
        if not procedure_ids:
            log.info("No procedures, no estimates.")
            return set()
        estimates = self.billing_service.get_estimates_by_procedure_ids(procedure_ids)
        estimate_procedure_ids = {e.procedure_id for e in estimates}
        to_return = set(procedure_ids) - estimate_procedure_ids
        log.info(
            "Procedures without estimates.",
            procedure_ids=procedure_ids,
            estimate_procedure_ids=estimate_procedure_ids,
            procedures_without_estimates=to_return,
        )
        return to_return

    def return_relevant_cost_breakdowns(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, procedure_uuid, expected_cost_breakdown_id
    ) -> Tuple[CostBreakdown | None, CostBreakdown | None]:
        """
        We require both the cost breakdown linked to the bill and the most recent past cost breakdown if it exists.
        In the golden path, this query should only ever return 1-2 cost breakdowns, but we can't promise that limit.
        Adding a log so we can track this if it gets out of hand.
        """
        # Using a direct query since there doesn't seem to be a repository
        session = CostBreakdown.query.session
        cost_breakdowns = (
            session.query(CostBreakdown)
            .filter(
                CostBreakdown.treatment_procedure_uuid == procedure_uuid,
                or_(
                    CostBreakdown.id == expected_cost_breakdown_id,
                    (
                        CostBreakdown.created_at
                        <= session.query(CostBreakdown.created_at).filter(
                            CostBreakdown.id == expected_cost_breakdown_id
                        )
                    ),
                ),
            )
            .order_by(CostBreakdown.created_at.desc())
            .limit(2)
            .all()
        )
        c_b_iter = iter(cost_breakdowns)
        return next(c_b_iter, None), next(c_b_iter, None)

    def return_credit_use_bool_for_procedure(
        self, procedure: TreatmentProcedure
    ) -> bool:
        session = ReimbursementOrgSettingCategoryAssociation.query.session
        benefit_type = (
            session.query(ReimbursementOrgSettingCategoryAssociation.benefit_type)
            .join(
                ReimbursementOrgSettingCategoryAssociation.reimbursement_organization_settings,
                ReimbursementOrganizationSettings.reimbursement_wallets,
            )
            .filter(
                ReimbursementOrgSettingCategoryAssociation.reimbursement_request_category_id
                == procedure.reimbursement_request_category_id,
                ReimbursementWallet.id == procedure.reimbursement_wallet_id,
            )
            .scalar()
        )
        return benefit_type == BenefitTypes.CYCLE

    def return_relevant_clinic_names(
        self, fertility_clinic_location_id: int
    ) -> Tuple[str, str]:
        clinic_loc = self.clinic_loc_repo.get(
            fertility_clinic_location_id=fertility_clinic_location_id
        )
        if not clinic_loc:
            log.error(
                "Unexpected Treatment Procedure without Clinic information in payments.",
                fertility_clinic_location_id=fertility_clinic_location_id,
            )
            return "", ""
        return (
            clinic_loc.name,
            clinic_loc.fertility_clinic.name if clinic_loc.fertility_clinic else "",
        )

    def create_pending_payment_records(
        self, pending_procedure_ids: set, procedure_map: dict
    ) -> list[PaymentRecord]:
        pending_records = []
        for procedure_id in pending_procedure_ids:
            procedure: TreatmentProcedure = procedure_map.get(procedure_id)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[Any]", variable has type "TreatmentProcedure")
            pending_records.append(self._create_pending_payment_record(procedure))
        return pending_records

    def create_pending_payment_records_for_reimbursement_wallet(
        self, pending_procedure_ids: set, procedure_map: dict
    ) -> list[PaymentRecordForReimbursementWallet]:
        pending_records = []
        for procedure_id in pending_procedure_ids:
            procedure: TreatmentProcedure = procedure_map.get(procedure_id)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[Any]", variable has type "TreatmentProcedure")
            pending_records.append(
                self._create_pending_payment_record_for_reimbursement_wallet(procedure)
            )
        return pending_records

    def create_payment_records(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        bills,
        procedure_map,
        cost_breakdown_map,
        allow_voided_payment_status: bool = False,
    ) -> list[PaymentRecord]:
        records = []
        for bill in bills:
            procedure: TreatmentProcedure = procedure_map.get(bill.procedure_id)
            cost_breakdown: CostBreakdown = cost_breakdown_map.get(
                bill.cost_breakdown_id
            )
            if procedure is None or cost_breakdown is None:
                log.error(
                    "Missing payment record supporting data. Skipped displaying bill.",
                    bill_id=bill.id,
                    procedure_id=bill.procedure_id,
                    cost_breakdown_id=bill.cost_breakdown_id,
                )
                continue
            records.append(
                self._create_payment_record(
                    bill, procedure, cost_breakdown, allow_voided_payment_status
                )
            )
        return records

    def create_upcoming_payment_records_for_reimbursement_wallet(
        self,
        bills: list[billing_models.Bill],
        procedure_map: dict,
        cost_breakdown_map: dict,
    ) -> list[PaymentRecordForReimbursementWallet]:
        records = []
        for bill in bills:
            procedure: TreatmentProcedure = procedure_map.get(bill.procedure_id)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[Any]", variable has type "TreatmentProcedure")
            cost_breakdown: CostBreakdown = cost_breakdown_map.get(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[Any]", variable has type "CostBreakdown")
                bill.cost_breakdown_id
            )
            if procedure is None or cost_breakdown is None:
                log.error(
                    "Missing supporting data to create the PaymentRecordForReimbursementWallet. Skipping the bill.",
                    bill_id=bill.id,
                    procedure_id=bill.procedure_id,
                    cost_breakdown_id=bill.cost_breakdown_id,
                )
                continue
            records.append(
                self._create_payment_record_for_reimbursement_wallet(
                    bill, procedure, cost_breakdown
                )
            )
        return records

    @staticmethod
    def _create_pending_payment_record(procedure: TreatmentProcedure) -> PaymentRecord:
        return PaymentRecord(
            label=procedure.procedure_name,
            treatment_procedure_id=procedure.id,
            payment_status="PENDING",
            payment_method_type=billing_models.PaymentMethod.PAYMENT_GATEWAY,
            created_at=procedure.created_at,
        )

    @staticmethod
    def _create_pending_payment_record_for_reimbursement_wallet(
        procedure: TreatmentProcedure,
    ) -> PaymentRecordForReimbursementWallet:
        return PaymentRecordForReimbursementWallet(
            payment_status="PENDING",
            # This isn't the cost, is it?
            procedure_id=procedure.id,
            procedure_title=procedure.procedure_name,
            created_at=procedure.created_at,
        )

    def _create_payment_record(
        self,
        bill: billing_models.Bill,
        procedure: TreatmentProcedure,
        cost_breakdown: CostBreakdown,
        allow_voided_payment_status: bool = False,
    ) -> PaymentRecord:
        return PaymentRecord(
            label=procedure.procedure_name,
            treatment_procedure_id=procedure.id,
            bill_uuid=str(bill.uuid),
            payment_status=self._compute_bill_status(
                bill, procedure, allow_voided_payment_status
            ),
            created_at=procedure.created_at,
            payment_method_type=bill.payment_method,
            payment_method_display_label=bill.payment_method_label,  # type: ignore[arg-type] # Argument "payment_method_display_label" to "PaymentRecord" has incompatible type "Optional[str]"; expected "str"
            member_responsibility=bill.amount + bill.last_calculated_fee,
            total_cost=procedure.cost,
            cost_responsibility_type=self._calculate_cost_responsibility_type(
                cost_breakdown
            ),
            due_at=self._calculate_due_at(bill),
            completed_at=self._calculate_completed_at(bill),  # type: ignore[arg-type] # Argument "completed_at" to "PaymentRecord" has incompatible type "Optional[datetime]"; expected "datetime"
            display_date=self._calculate_display_date(bill),
        )

    @staticmethod
    def _compute_bill_status(
        bill: billing_models.Bill,
        procedure: TreatmentProcedure,
        allow_voided_payment_status: bool = False,
    ) -> PaymentStatusT:
        if (
            bill.status == billing_models.BillStatus.PAID
            and bill.amount == 0
            and procedure.status == TreatmentProcedureStatus.CANCELLED
        ):
            # allow_voided is set by a feature flag that checks whether the
            # client device is using a version after 2024.04
            # If we remove allow_voided, then this will workflow will break
            # on client devices that do not recognize "VOIDED" as an enum value
            return (
                "VOIDED"
                if allow_voided_payment_status
                else billing_models.BillStatus.CANCELLED.value
            )
        return bill.status.value

    def _create_payment_record_for_reimbursement_wallet(
        self,
        bill: billing_models.Bill,
        procedure: TreatmentProcedure,
        cost_breakdown: CostBreakdown,
    ) -> PaymentRecordForReimbursementWallet:
        due_at = self._calculate_due_at(bill)
        member_date = due_at.strftime("%Y-%m-%d")
        return PaymentRecordForReimbursementWallet(
            bill_uuid=str(bill.uuid),
            payment_status=bill.status.value,
            member_amount=bill.amount + bill.last_calculated_fee,
            member_method=bill.payment_method_label,
            member_date=member_date,
            benefit_amount=cost_breakdown.total_employer_responsibility,
            # Hard-coding the benefit_date to "" for now
            # This field might not be used in the client
            # and might be deprecated
            benefit_date="",
            benefit_remaining=cost_breakdown.ending_wallet_balance,
            error_type=bill.error_type,
            procedure_id=procedure.id,
            procedure_title=procedure.procedure_name,
            created_at=bill.created_at,
            due_at=due_at,
            processing_scheduled_at_or_after=bill.processing_scheduled_at_or_after,
        )

    def create_payment_detail(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        bill: billing_models.Bill,
        past_bill_fees: int | None,
        procedure: TreatmentProcedure,
        cost_breakdown: CostBreakdown,
        past_cost_breakdown: CostBreakdown | None,
        clinic_name: str,
        clinic_loc_name: str,
        is_credit_based_wallet: bool = False,
        show_voided_payment_status: bool = False,
    ) -> PaymentDetail:
        is_adjusted_bill = (
            past_cost_breakdown is not None and past_bill_fees is not None
        )
        if is_credit_based_wallet:
            credits_used = (
                ReimbursementRequestRepository().get_num_credits_by_cost_breakdown_id(
                    cost_breakdown.id
                )
            )
        else:
            credits_used = None
        if cost_breakdown.coinsurance:
            coins_or_copay = PaymentDetailBreakdown(
                label=DetailLabel.COINSURANCE.value,
                cost=cost_breakdown.coinsurance,
                original=past_cost_breakdown.coinsurance if is_adjusted_bill else None,  # type: ignore[union-attr] # Item "None" of "Optional[CostBreakdown]" has no attribute "coinsurance"
            )
        else:
            coins_or_copay = PaymentDetailBreakdown(
                label=DetailLabel.COPAY.value,
                cost=cost_breakdown.copay,
                original=past_cost_breakdown.copay if is_adjusted_bill else None,  # type: ignore[union-attr] # Item "None" of "Optional[CostBreakdown]" has no attribute "copay"
            )

        responsibility = [
            PaymentDetailBreakdown(
                label=DetailLabel.DEDUCTIBLE.value,
                cost=cost_breakdown.deductible,
                original=past_cost_breakdown.deductible if is_adjusted_bill else None,  # type: ignore[union-attr] # Item "None" of "Optional[CostBreakdown]" has no attribute "deductible"
            ),
            coins_or_copay,
        ]
        if cost_breakdown.hra_applied is not None and cost_breakdown.hra_applied > 0:
            responsibility.append(
                PaymentDetailBreakdown(
                    label=DetailLabel.HRA_APPLIED.value,
                    cost=-cost_breakdown.hra_applied,
                    original=(
                        -past_cost_breakdown.hra_applied if is_adjusted_bill else None  # type: ignore[union-attr,arg-type] # Item "None" of "Optional[CostBreakdown]" has no attribute "hra_applied" #type: ignore[arg-type] # Argument "original" to "PaymentDetailBreakdown" has incompatible type "Union[int, Any, None]"; expected "int"
                    ),
                )
            )
        if (bill.last_calculated_fee is not None and bill.last_calculated_fee > 0) or (
            past_bill_fees is not None and past_bill_fees > 0
        ):
            responsibility.append(
                PaymentDetailBreakdown(
                    label=DetailLabel.FEES.value,
                    cost=(bill.last_calculated_fee or 0) + (past_bill_fees or 0),
                    original=past_bill_fees,
                )
            )
        if cost_breakdown.overage_amount > 0:
            responsibility.append(
                PaymentDetailBreakdown(
                    label=DetailLabel.NOT_COVERED.value,
                    cost=cost_breakdown.overage_amount,
                    original=(
                        past_cost_breakdown.overage_amount if is_adjusted_bill else None  # type: ignore[union-attr,arg-type] # Item "None" of "Optional[CostBreakdown]" has no attribute "overage_amount" #type: ignore[arg-type] # Argument "original" to "PaymentDetailBreakdown" has incompatible type "Union[int, Any, None]"; expected "int"
                    ),
                )
            )
        benefit = [
            PaymentDetailBreakdown(
                label=DetailLabel.MAVEN_BENEFIT.value,
                cost=cost_breakdown.total_employer_responsibility,
                original=(
                    past_cost_breakdown.total_employer_responsibility  # type: ignore[union-attr,arg-type] # Item "None" of "Optional[CostBreakdown]" has no attribute "total_employer_responsibility" #type: ignore[arg-type] # Argument "original" to "PaymentDetailBreakdown" has incompatible type "Union[int, Any, None]"; expected "int"
                    if is_adjusted_bill
                    else None
                ),
            ),
            PaymentDetailBreakdown(
                label=DetailLabel.MEDICAL_PLAN.value,
                cost=0,
                original=0 if is_adjusted_bill else None,  # type: ignore[arg-type] # Argument "original" to "PaymentDetailBreakdown" has incompatible type "Optional[int]"; expected "int"
            ),
        ]
        if cost_breakdown.hra_applied is not None and cost_breakdown.hra_applied > 0:
            benefit.append(
                PaymentDetailBreakdown(
                    label=DetailLabel.HRA_CREDIT.value,
                    cost=cost_breakdown.hra_applied,
                    original=(
                        past_cost_breakdown.hra_applied if is_adjusted_bill else None  # type: ignore[union-attr,arg-type] # Item "None" of "Optional[CostBreakdown]" has no attribute "hra_applied" #type: ignore[arg-type] # Argument "original" to "PaymentDetailBreakdown" has incompatible type "Union[int, Any, None]"; expected "int"
                    ),
                )
            )
        return PaymentDetail(
            label=procedure.procedure_name,
            treatment_procedure_id=bill.procedure_id,
            treatment_procedure_clinic=clinic_name,
            treatment_procedure_location=clinic_loc_name,
            treatment_procedure_started_at=procedure.start_date,  # type: ignore[arg-type] # Argument "treatment_procedure_started_at" to "PaymentDetail" has incompatible type "Optional[date]"; expected "date"
            payment_status=self._compute_bill_status(
                bill, procedure, show_voided_payment_status
            ),
            member_responsibility=bill.amount + bill.last_calculated_fee,
            total_cost=procedure.cost,
            cost_responsibility_type=self._calculate_cost_responsibility_type(
                cost_breakdown
            ),
            error_type=bill.error_type,  # type: ignore[arg-type] # Argument "error_type" to "PaymentDetail" has incompatible type "Optional[str]"; expected "str"
            responsibility_breakdown=list(responsibility),
            benefit_breakdown=benefit,
            credits_used=abs(credits_used) if credits_used is not None else None,
            created_at=procedure.created_at,  # TODO: is this used?
            due_at=self._calculate_due_at(bill),
            completed_at=self._calculate_completed_at(bill),  # type: ignore[arg-type] # Argument "completed_at" to "PaymentDetail" has incompatible type "Optional[datetime]"; expected "datetime"
            procedure_status=procedure.status.value,  # type: ignore[attr-defined] # "str" has no attribute "value"
        )

    def support_app_version(self, request_headers: dict, version: str) -> bool:
        """
        Check whether user's app version is higher or equal to the input version.
        """
        # we return True for web request
        if not self.is_android(request_headers=request_headers) and not self.is_iOS(
            request_headers=request_headers
        ):
            return True

        user_app_version = request_headers["User-Agent"].split(" ")[0].split("/")[1]
        return user_app_version >= version

    def is_iOS(self, request_headers: dict) -> bool:
        """
        Return if the client device is an iOS device, which might be iPhone or iPad.
        """
        return "iOS" in request_headers.get("User-Agent", "")

    def is_android(self, request_headers: dict) -> bool:
        """
        Return if the client device is an Android device.
        """
        return "Android" in request_headers.get("User-Agent", "")

    def show_payment_status_voided(
        self, request_headers: dict, use_refunds_refinement: bool
    ) -> bool:
        """
        Return true if Android or iOS's app version is equal or greater than 202406.2.0.
        """
        if use_refunds_refinement and self.support_app_version(
            request_headers=request_headers, version="202406.2.0"
        ):
            return True
        return False

    @staticmethod
    def _calculate_due_at(bill: billing_models.Bill) -> datetime.datetime:
        # Note: This is an estimated due date due to the nature of the member charge cronjob and timezones.
        if not (to_return := bill.processing_scheduled_at_or_after):
            # for backwards compatibility
            to_return = (
                bill.created_at
                + datetime.timedelta(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Union[datetime, timedelta]", variable has type "Optional[datetime]")
                    days=MEMBER_BILLING_OFFSET_DAYS
                )
            )
        return to_return  # type: ignore[return-value] # Incompatible return value type (got "Optional[datetime]", expected "datetime")

    @staticmethod
    def _calculate_cost_responsibility_type(
        cost_breakdown: CostBreakdown,
    ) -> CostResponsibilityT:
        if (
            cost_breakdown.total_member_responsibility == 0
            and cost_breakdown.total_employer_responsibility != 0
        ):
            return "no_member"
        if (
            cost_breakdown.total_member_responsibility != 0
            and cost_breakdown.total_employer_responsibility == 0
        ):
            return "member_only"
        return "shared"

    @staticmethod
    def _calculate_completed_at(bill: billing_models.Bill) -> datetime.datetime | None:  # type: ignore[return] # Missing return statement
        if bill.status == billing_models.BillStatus.PAID:
            return bill.paid_at
        if bill.status == billing_models.BillStatus.REFUNDED:
            return bill.refunded_at

    @staticmethod
    def _calculate_display_date(
        bill: billing_models.Bill | None = None,
    ) -> DisplayDatesT:
        if bill and bill.status in billing_models.HISTORIC_STATUS:
            return "completed_at"
        if bill and bill.status in billing_models.UPCOMING_STATUS:
            return "due_at"
        return "created_at"
