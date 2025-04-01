from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from traceback import format_exc
from typing import Optional

from authn.models.user import User
from common.global_procedures.procedure import GlobalProcedure
from direct_payment.pharmacy.constants import (
    REIMBURSEMENT_FILE_TYPE,
    SMP_ACTUAL_SHIP_DATE,
    SMP_AMOUNT_PAID,
    SMP_DRUG_DESCRIPTION,
    SMP_DRUG_NAME,
    SMP_FIRST_NAME,
    SMP_LAST_NAME,
    SMP_MAVEN_USER_BENEFIT_ID,
    SMP_NCPDP_NUMBER,
    SMP_NDC_NUMBER,
    SMP_REIMBURSEMENT_FILE_PREFIX,
    SMP_RX_FILLED_DATE,
    SMP_RX_ORDER_ID,
    SMP_RX_RECEIVED_DATE,
    SMP_UNIQUE_IDENTIFIER,
)
from direct_payment.pharmacy.models.pharmacy_prescription import (
    PrescriptionStatus,
    ReimbursementPharmacyPrescriptionParams,
    ReimbursementRequestParams,
)
from direct_payment.pharmacy.tasks.libs.rx_file_processor import FileProcessor
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator.accumulation_mapping_service import AccumulationMappingService
from storage.connection import db
from utils.log import logger
from utils.payments import convert_dollars_to_cents
from wallet.models.constants import (
    CostSharingCategory,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    WalletUserMemberStatus,
)
from wallet.models.reimbursement import WalletExpenseSubtype
from wallet.utils.events import send_reimbursement_request_state_event

REIMBURSEMENT_FILE_EXPECTED_FIELDS = [
    SMP_NCPDP_NUMBER,
    SMP_FIRST_NAME,
    SMP_LAST_NAME,
    SMP_NDC_NUMBER,
    SMP_DRUG_NAME,
    SMP_UNIQUE_IDENTIFIER,
    SMP_DRUG_DESCRIPTION,
    SMP_RX_RECEIVED_DATE,
    SMP_RX_ORDER_ID,
    SMP_MAVEN_USER_BENEFIT_ID,
    SMP_RX_FILLED_DATE,
]

log = logger(__name__)

JOB_NAME = "smp_process_reimbursement_file"
SMP_PHARMACY = "SMP Pharmacy"
RX_EXPENSE_SUBTYPE_CODE = "FERTRX"


class ReimbursementFileProcessor(FileProcessor):
    def __init__(self, dry_run: bool = False):
        super().__init__(dry_run)
        self.file_type: Optional[str] = REIMBURSEMENT_FILE_TYPE
        self.job_name: Optional[str] = JOB_NAME
        self.expected_fields: Optional[list] = REIMBURSEMENT_FILE_EXPECTED_FIELDS
        self.last_rx_date_timestamp: dict = {}

    def get_file_prefix(self) -> str:
        return SMP_REIMBURSEMENT_FILE_PREFIX

    def get_benefit_id(self, row: dict) -> str:
        return row[SMP_MAVEN_USER_BENEFIT_ID]

    def handle_row(self, row: dict) -> None:
        benefit_id = self.get_benefit_id(row=row)
        cost = convert_dollars_to_cents(float(row[SMP_AMOUNT_PAID]))
        pharmacy_prescription = self.get_pharmacy_prescription(row=row)
        if pharmacy_prescription:
            log.info(
                f"{self.job_name}: Found existing Prescription.",
                reimbursement_request_id=pharmacy_prescription.reimbursement_request_id,
                pharmacy_prescription_id=pharmacy_prescription.id,
                unique_id=row[SMP_UNIQUE_IDENTIFIER],
            )
        else:
            prescription_params = ReimbursementPharmacyPrescriptionParams(
                user_benefit_id=benefit_id,
                status=PrescriptionStatus.PAID,
                amount_owed=cost,
                actual_ship_date=datetime.strptime(
                    row[SMP_ACTUAL_SHIP_DATE], "%m/%d/%Y"
                ),
                rx_filled_date=datetime.strptime(row[SMP_RX_FILLED_DATE], "%m/%d/%Y"),
                reimbursement_json=row,
            )
            pharmacy_prescription = self.create_pharmacy_prescription(
                row=row, prescription_params=dataclasses.asdict(prescription_params)
            )
            log.info(
                f"{self.job_name}: Pharmacy Prescription initial record created.",
                pharmacy_prescription_id=pharmacy_prescription.id,
                user_benefit_id=benefit_id,
            )

        reimbursement_request = (
            self.auto_reimbursement_request_service.get_reimbursement_request(
                pharmacy_prescription=pharmacy_prescription
            )
        )
        if reimbursement_request:
            log.info(
                f"{self.job_name}: Skipping processing found existing Reimbursement Request.",
                reimbursement_request_id=pharmacy_prescription.reimbursement_request_id,
                pharmacy_prescription_id=pharmacy_prescription.id,
                unique_id=row[SMP_UNIQUE_IDENTIFIER],
            )
            return

        if not (global_procedure := self.validate_global_procedure(row)):
            return

        state = ReimbursementRequestState.NEW
        # Validate data to create NEW Reimbursement Request else create a Denied Reimbursement Request

        base_wallet = self.validate_wallet(row)
        if not base_wallet:
            return

        wallet = self.validate_wallet_state(base_wallet, row)
        if wallet is None:
            state = ReimbursementRequestState.DENIED
            wallet = base_wallet

        user = self.validate_user(row, wallet)

        org_settings = self.validate_org_settings(
            row=row, rx_enabled=False, wallet=wallet, user=user
        )

        category = self.validate_category(row, wallet)
        if category is None:
            # Unable to find direct payment category - selecting any category to deny Reimbursement Request
            state = ReimbursementRequestState.DENIED
            category = self.get_default_category(wallet=wallet)

            if category is None:
                self.failed_rows.append(
                    (
                        benefit_id,
                        row[SMP_UNIQUE_IDENTIFIER],
                        "Could not find a category for the wallet.",
                    )
                )
                log.error(
                    "Could not find a category for the wallet.",
                    maven_member_id=benefit_id,
                    wallet_id=str(wallet.id),
                )
                return

        clinic = self.validate_fertility_clinic(row)
        clinic_name = clinic.name if clinic else SMP_PHARMACY

        cost_sharing_category = self.validate_cost_sharing_category(
            row, global_procedure
        )

        wallet_balance = self.validate_wallet_balance(row, wallet, category)

        if any(
            not valid_object
            for valid_object in [
                wallet,
                user,
                org_settings,
                cost_sharing_category,
                wallet_balance,
            ]
        ):
            state = ReimbursementRequestState.DENIED

        expense_type = (
            self.auto_reimbursement_request_service.return_category_expense_type(
                category=category
            )
        )
        if expense_type is None:
            expense_type = ReimbursementRequestExpenseTypes.FERTILITY

        wallet_expense_subtype: WalletExpenseSubtype | None = self.auto_reimbursement_request_service.reimbursement_request_service.get_expense_subtype(
            expense_type=expense_type, code=RX_EXPENSE_SUBTYPE_CODE
        )

        if wallet_expense_subtype is None:
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Could not find wallet expense subtype",
                )
            )
            log.error(
                "Could not find wallet expense subtype",
                maven_member_id=benefit_id,
                expense_type=expense_type,
                code=RX_EXPENSE_SUBTYPE_CODE,
            )
            return

        try:
            member_status = (
                self.auto_reimbursement_request_service.get_member_status(
                    user_id=user.id, wallet_id=wallet.id
                )
                if user and wallet
                else None
            )
            request_params = self._create_reimbursement_request_params(
                row=row,
                clinic_name=clinic_name,
                cost=cost,
                state=state,
                user=user,
                member_status=member_status,
                cost_sharing_category=cost_sharing_category,
                expense_type=expense_type,
                wallet_expense_subtype=wallet_expense_subtype,
                global_procedure=global_procedure,
            )
            reimbursement_request = (
                self.auto_reimbursement_request_service.create_reimbursement_request(
                    wallet=wallet,
                    category=category,
                    request_params=dataclasses.asdict(request_params),
                )
            )
            db.session.add(reimbursement_request)
            db.session.commit()
            pharmacy_params = {
                "reimbursement_request_id": reimbursement_request.id,
                "user_id": user.id if user else None,
            }
            self.update_pharmacy_prescription(
                prescription=pharmacy_prescription,
                prescription_params=pharmacy_params,
            )
        except Exception as e:
            log.exception(
                f"{self.job_name}: Exception saving data objects.",
                maven_member_id=benefit_id,
                error=e,
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Could not save object.",
                )
            )
            return

        # Checks for Denied or duplicate reimbursement request
        if reimbursement_request.state == ReimbursementRequestState.DENIED:
            log.info(
                "Reimbursement Request created in the Denied state due to validation failure.",
                reimbursement_request_id=str(reimbursement_request.id),
                wallet_id=str(wallet.id),
            )
            send_reimbursement_request_state_event(reimbursement_request)
            return

        if self.auto_reimbursement_request_service.check_for_duplicate_automated_rx_reimbursement(
            reimbursement_request
        ):
            log.info(
                "Reimbursement Request created in the NEW state due to duplication detection.",
                reimbursement_request_id=str(reimbursement_request.id),
                wallet_id=str(wallet.id),
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Duplicate Reimbursement Request found.",
                )
            )
            return
        # Run cost breakdown for new reimbursement request
        original_reimbursement_amount = reimbursement_request.amount
        try:
            cost_breakdown = self.auto_reimbursement_request_service.get_reimbursement_request_cost_breakdown(
                reimbursement_request=reimbursement_request, user_id=user.id  # type: ignore[union-attr]
            )
            db.session.add(cost_breakdown)
            db.session.commit()
            log.info(
                f"{self.job_name}: Cost breakdown created for reimbursement request.",
                reimbursement_request_id=str(reimbursement_request.id),
                cost_breakdown_id=str(cost_breakdown.id),
            )
        except Exception as e:
            log.exception(
                f"{self.job_name}: Exception running cost breakdown.",
                maven_member_id=benefit_id,
                error=e,
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Error running Cost Breakdown.",
                )
            )
            self.auto_reimbursement_request_service.reset_reimbursement_request(
                reimbursement_request=reimbursement_request,
                original_amount=original_reimbursement_amount,
                cost_breakdown=None,
            )
            return
        # Submit reimbursement request to Alegeus as a claim
        try:
            reimbursement_method = (
                self.auto_reimbursement_request_service.get_reimbursement_method(
                    wallet=wallet, expense_type=expense_type
                )
            )
            self.auto_reimbursement_request_service.submit_auto_processed_request_to_alegeus(
                reimbursement_request=reimbursement_request,
                cost_breakdown=cost_breakdown,
                wallet=wallet,
                reimbursement_method=reimbursement_method,
            )
            self.processed_row_count += 1
        except Exception as e:
            log.error(
                f"{self.job_name}: Alegeus Request Failed to submit transaction for auto reimbursement.",
                maven_member_id=benefit_id,
                error=e,
                error_details=format_exc(),
                reimbursement_request_id=str(reimbursement_request.id),
                reimbursement_wallet_id=str(wallet.id),
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Failed to submit auto processed claim to Alegeus.",
                )
            )
            self.auto_reimbursement_request_service.reset_reimbursement_request(
                reimbursement_request=reimbursement_request,
                original_amount=original_reimbursement_amount,
                cost_breakdown=cost_breakdown,
            )
            return
        # Add accumulation mapping for newly created Reimbursement Request if necessary
        try:
            ams = AccumulationMappingService(db.session)
            is_valid = ams.reimbursement_request_is_valid_for_accumulation(
                reimbursement_request
            )
            should_accumulate = self.auto_reimbursement_request_service.should_accumulate_automated_rx_reimbursement_request(
                reimbursement_request, cost_breakdown
            )
            if should_accumulate and is_valid:
                mapping = ams.create_valid_reimbursement_request_mapping(
                    reimbursement_request=reimbursement_request
                )
                db.session.add(mapping)
                db.session.commit()
        except Exception as e:
            #  Don't reset reimbursement request on failure, just alert and we can manually create a mapping
            log.exception(
                f"{self.job_name}: Exception adding accumulation mapping for reimbursement request.",
                maven_member_id=benefit_id,
                error=e,
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Error creating accumulation mapping.",
                )
            )
            return

    def get_next_rx_timestamp(self, rx_received_date: str) -> datetime:
        """Returns sequential timestamps for same RX received date"""
        base_date = datetime.strptime(rx_received_date, "%m/%d/%Y")
        next_timestamp = self.last_rx_date_timestamp.get(base_date)
        self.last_rx_date_timestamp[base_date] = (
            next_timestamp + timedelta(seconds=1) if next_timestamp else base_date
        )
        return self.last_rx_date_timestamp[base_date]

    def _create_reimbursement_request_params(
        self,
        row: dict,
        clinic_name: str,
        cost: int,
        state: ReimbursementRequestState,
        user: Optional[User] = None,
        member_status: Optional[WalletUserMemberStatus] = None,
        cost_sharing_category: Optional[CostSharingCategory] = None,
        expense_type: Optional[ReimbursementRequestExpenseTypes] = None,
        wallet_expense_subtype: Optional[WalletExpenseSubtype] = None,
        global_procedure: Optional[GlobalProcedure] = None,
    ) -> ReimbursementRequestParams:
        service_date = self.get_next_rx_timestamp(row[SMP_RX_RECEIVED_DATE])

        return ReimbursementRequestParams(
            label=row[SMP_DRUG_NAME],
            service_provider=clinic_name,
            person_receiving_service=user.full_name if user else None,
            person_receiving_service_id=user.id if user else None,
            person_receiving_service_member_status=member_status,
            amount=cost,
            service_start_date=service_date,
            service_end_date=service_date,
            reimbursement_type=ReimbursementRequestType.MANUAL,
            state=state,
            cost_sharing_category=cost_sharing_category,
            procedure_type=TreatmentProcedureType.PHARMACY.value,
            expense_type=expense_type,
            original_wallet_expense_subtype_id=wallet_expense_subtype.id
            if wallet_expense_subtype
            else None,
            wallet_expense_subtype_id=wallet_expense_subtype.id
            if wallet_expense_subtype
            else None,
            cost_credit=global_procedure["credits"] if global_procedure else None,
            auto_processed=ReimbursementRequestAutoProcessing.RX,
        )
