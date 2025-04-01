from __future__ import annotations

import csv
import datetime
import io
from abc import ABC, abstractmethod
from typing import IO, Any, Optional, Union

from maven import feature_flags

from authn.models.user import User
from common.global_procedures.constants import UNAUTHENTICATED_PROCEDURE_SERVICE_URL
from common.global_procedures.procedure import GlobalProcedure, ProcedureService
from direct_payment.clinic.models.clinic import FertilityClinic
from direct_payment.pharmacy.automated_reimbursement_request_service import (
    AutomatedReimbursementRequestService,
)
from direct_payment.pharmacy.constants import (
    ENABLE_SMP_GCS_BUCKET_PROCESSING,
    ENABLE_UNLIMITED_BENEFITS_FOR_SMP,
    QUATRIX_OUTBOUND_BUCKET,
    REIMBURSEMENT_FILE_TYPE,
    RX_NCPDP_ID_TO_FERTILITY_CLINIC_NAME,
    SMP_DRUG_DESCRIPTION,
    SMP_DRUG_NAME,
    SMP_FIRST_NAME,
    SMP_GCP_BUCKET_NAME,
    SMP_LAST_NAME,
    SMP_NCPDP_NUMBER,
    SMP_NDC_NUMBER,
    SMP_RX_ORDER_ID,
    SMP_RX_RECEIVED_DATE,
    SMP_UNIQUE_IDENTIFIER,
)
from direct_payment.pharmacy.models.pharmacy_prescription import PharmacyPrescription
from direct_payment.pharmacy.pharmacy_prescription_service import (
    PharmacyPrescriptionService,
)
from direct_payment.pharmacy.tasks.libs.common import (
    IS_INTEGRATIONS_K8S_CLUSTER,
    _send_file_receipt,
    convert_to_string_io,
    get_global_procedure,
    get_smp_ingestion_file,
    get_wallet_user,
    raw_rows_count,
    validate_file,
)
from direct_payment.pharmacy.tasks.libs.pharmacy_file_handler import PharmacyFileHandler
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
)
from storage.connection import db
from utils.log import logger
from wallet.models.constants import CostSharingCategory, WalletState
from wallet.models.models import CategoryBalance
from wallet.models.reimbursement import ReimbursementRequestCategory
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_benefit import ReimbursementWalletBenefit
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.repository.member_benefit import MemberBenefitRepository
from wallet.services.reimbursement_wallet import ReimbursementWalletService

log = logger(__name__)


class FileProcessor(ABC):
    def __init__(self, dry_run: bool = False):
        self.dry_run: bool = dry_run
        self.file_type: Optional[str] = None
        self.job_name: Optional[str] = None
        self.expected_fields: Optional[list] = None
        self.failed_rows: list = []
        self.processed_row_count: int = 0
        self.pharmacy_prescription_service = PharmacyPrescriptionService(
            session=db.session, is_in_uow=False
        )
        self.auto_reimbursement_request_service = AutomatedReimbursementRequestService()
        self.wallet_service = ReimbursementWalletService()
        self.enable_unlimited_benefits_for_smp: bool = feature_flags.bool_variation(
            ENABLE_UNLIMITED_BENEFITS_FOR_SMP, default=False
        )
        self.member_benefit_repo = MemberBenefitRepository(session=db.session)
        if IS_INTEGRATIONS_K8S_CLUSTER:
            self.procedure_service_client = ProcedureService(
                base_url=UNAUTHENTICATED_PROCEDURE_SERVICE_URL
            )
        else:
            self.procedure_service_client = ProcedureService(internal=True)

    @abstractmethod
    def handle_row(self, row: dict) -> Any:
        raise NotImplementedError("Missing handle row method.")

    @abstractmethod
    def get_file_prefix(self) -> Any:
        raise NotImplementedError("Missing get_file_prefix method.")

    def get_benefit_id(self, row: dict) -> Any:
        raise NotImplementedError("Missing benefit id method.")

    def process_file(self, file: Union[IO[str], IO[bytes]]) -> None:
        string_file = convert_to_string_io(file)
        row_count = raw_rows_count(string_file)

        if self.dry_run:
            log.info(
                f"{self.job_name}: DRY RUN {row_count} rows of data to be processed."
            )
            return

        for raw_row in csv.DictReader(string_file):
            self.process_row(raw_row)

        if self.failed_rows:
            log.error(
                f"{self.job_name}: SMP {self.file_type} file contains unprocessable member records.",
                failure_list="; ".join(
                    ", ".join(inner_list) for inner_list in self.failed_rows
                ),
            )
        log.info(
            f"{self.job_name}: Processing report",
            total_records=row_count,
            processed_records=self.processed_row_count,
            job_name=self.job_name,
        )

    def process_row(self, raw_row: dict) -> None:
        try:
            row = self.validated_row_data(raw_row=raw_row)
            if not row:
                return

            self.handle_row(row)

        except Exception as e:
            log.exception(
                f"{self.job_name}: Exception processing SMP {self.file_type} file row.",
                error=e,
            )
            self.failed_rows.append(
                (
                    self.get_benefit_id(row=raw_row),
                    raw_row[SMP_UNIQUE_IDENTIFIER],
                    "Unable to process row. Event raised to engineering for review.",
                )
            )
            return

    def validated_row_data(self, raw_row: dict) -> dict | None:
        """Validates ingested required data is not empty."""
        cleaned_row = {}
        for key, value in raw_row.items():
            cleaned_row[key.strip()] = value.strip()
            if key.strip() in self.expected_fields:
                if not value:
                    log.error(
                        f"SMP {self.file_type} ingestion file is missing a value for {key}."
                    )
                    self.failed_rows.append(
                        (
                            self.get_benefit_id(row=raw_row),
                            raw_row[SMP_UNIQUE_IDENTIFIER],
                            "Missing required data in record.",
                        )
                    )
                    return None
        return cleaned_row

    def validate_wallet(self, row: dict) -> ReimbursementWallet | None:
        benefit_id = self.get_benefit_id(row=row)
        allowed_wallet_states = [WalletState.QUALIFIED, WalletState.RUNOUT]
        wallet = None
        if self.file_type == REIMBURSEMENT_FILE_TYPE:
            try:
                member_benefit = self.member_benefit_repo.get_by_benefit_id(
                    benefit_id=benefit_id
                )
                wallet = (
                    db.session.query(ReimbursementWallet)
                    .join(
                        ReimbursementWalletUsers,
                        ReimbursementWallet.id
                        == ReimbursementWalletUsers.reimbursement_wallet_id,
                    )
                    .filter(
                        ReimbursementWalletUsers.user_id == member_benefit.user_id,
                        ReimbursementWallet.state.in_(allowed_wallet_states),
                    )
                    .one_or_none()
                )
            except Exception as e:
                log.exception(
                    f"{self.job_name}: Exception validating wallet.",
                    benefit_id=benefit_id,
                    error=e,
                )
        else:
            wallet = (
                db.session.query(ReimbursementWallet)
                .join(ReimbursementWalletBenefit)
                .filter(
                    ReimbursementWalletBenefit.maven_benefit_id == benefit_id,
                    ReimbursementWallet.state.in_(allowed_wallet_states),
                )
                .one_or_none()
            )
        if not wallet:
            log.error(f"{self.job_name}: Wallet not found.", benefit_id=benefit_id)
            self.failed_rows.append(
                (benefit_id, row[SMP_UNIQUE_IDENTIFIER], "Wallet not found.")
            )
            return None
        return wallet

    def validate_wallet_state(
        self, wallet: ReimbursementWallet, row: dict
    ) -> ReimbursementWallet | None:
        benefit_id = self.get_benefit_id(row=row)
        if wallet.state not in [WalletState.QUALIFIED, WalletState.RUNOUT]:
            log.error(
                f"{self.job_name}: Wallet state not allowed for auto processed reimbursements.",
                benefit_id=benefit_id,
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Wallet state not allowed for auto processed reimbursements.",
                )
            )
            return None
        return wallet

    def validate_user(
        self, row: dict, wallet: Optional[ReimbursementWallet]
    ) -> User | None:
        benefit_id = self.get_benefit_id(row=row)
        user = None
        if wallet:
            user = get_wallet_user(wallet, row[SMP_FIRST_NAME], row[SMP_LAST_NAME])
            if not user:
                log.error(
                    f"{self.job_name}: Could not find User.",
                    benefit_id=benefit_id,
                    wallet_id=str(wallet.id),
                )
                if not any(
                    failed_row[1] == row[SMP_UNIQUE_IDENTIFIER]
                    for failed_row in self.failed_rows
                ):
                    self.failed_rows.append(
                        (benefit_id, row[SMP_UNIQUE_IDENTIFIER], "User not found.")
                    )
        return user

    def validate_org_settings(
        self,
        row: dict,
        rx_enabled: bool,
        wallet: Optional[ReimbursementWallet],
        user: Optional[User],
    ) -> ReimbursementOrganizationSettings | None:
        benefit_id = self.get_benefit_id(row=row)
        if user and wallet:
            org_setting = wallet.reimbursement_organization_settings
            if (
                org_setting.rx_direct_payment_enabled == rx_enabled
                and org_setting.direct_payment_enabled
                and user.member_profile
                and user.member_profile.country_code == "US"
            ):
                return org_setting
            else:
                log.error(
                    f"{self.job_name}: Member configuration not available for action.",
                    wallet_state=wallet.state,
                    rx_enabled=org_setting.rx_direct_payment_enabled,
                    benefit_id=benefit_id,
                    user_id=user.id,
                )
                if not any(
                    failed_row[1] == row[SMP_UNIQUE_IDENTIFIER]
                    for failed_row in self.failed_rows
                ):
                    self.failed_rows.append(
                        (
                            benefit_id,
                            row[SMP_UNIQUE_IDENTIFIER],
                            "Problem with configurations.",
                        )
                    )
        return None

    def validate_fertility_clinic(self, row: dict) -> Optional[FertilityClinic]:
        benefit_id = self.get_benefit_id(row=row)
        fertility_clinic_name = RX_NCPDP_ID_TO_FERTILITY_CLINIC_NAME.get(
            row[SMP_NCPDP_NUMBER]
        )
        clinic = FertilityClinic.query.filter_by(
            name=fertility_clinic_name
        ).one_or_none()
        if not clinic:
            log.error(
                f"{self.job_name}: Fertility Clinic not found.",
                fertility_clinic_id=fertility_clinic_name,
                smp_ncpdp_number=row[SMP_NCPDP_NUMBER],
            )
            if not any(
                failed_row[1] == row[SMP_UNIQUE_IDENTIFIER]
                for failed_row in self.failed_rows
            ):
                self.failed_rows.append(
                    (
                        benefit_id,
                        row[SMP_UNIQUE_IDENTIFIER],
                        "Fertility Clinic not found.",
                    )
                )
        return clinic

    def get_rx_received_date(self, row: dict) -> Optional[datetime.date]:
        rx_received_date_str = row[SMP_RX_RECEIVED_DATE]

        if rx_received_date_str is None:
            log.error(
                f"{self.get_benefit_id(row)}: No attribute '{SMP_RX_RECEIVED_DATE}' found in the row."
            )
            return None

        effective_date_datetime = datetime.datetime.strptime(
            rx_received_date_str, "%m/%d/%Y"
        )
        if effective_date_datetime is None:
            log.error(
                f"{self.get_benefit_id(row)}: Could not parse date '{rx_received_date_str}'. Expect MM/DD/YYYY."
            )
            return None

        return effective_date_datetime.date()

    def validate_global_procedure(self, row: dict) -> Optional[GlobalProcedure]:
        benefit_id = self.get_benefit_id(row=row)
        effective_date = self.get_rx_received_date(row=row)

        global_procedure = get_global_procedure(
            procedure_service_client=self.procedure_service_client,
            rx_ndc_number=row[SMP_NDC_NUMBER],
            start_date=effective_date,
            end_date=effective_date,
        )
        if not global_procedure:
            log.error(
                f"{self.job_name}: Could not find reimbursement wallet global procedure",
                global_procedure_ndc_number=row[SMP_NDC_NUMBER],
            )
            if not any(
                failed_row[1] == row[SMP_UNIQUE_IDENTIFIER]
                for failed_row in self.failed_rows
            ):
                self.failed_rows.append(
                    (
                        benefit_id,
                        row[SMP_UNIQUE_IDENTIFIER],
                        "Global Procedure not found.",
                    )
                )
        return global_procedure

    def validate_category(
        self, row: dict, wallet: ReimbursementWallet
    ) -> Optional[ReimbursementRequestCategory]:
        benefit_id = self.get_benefit_id(row=row)
        category = wallet.get_direct_payment_category
        if category is None:
            log.error(
                f"{self.job_name}: Reimbursement Request Category not found.",
                wallet_id=wallet.id,
            )
            if not any(
                failed_row[1] == row[SMP_UNIQUE_IDENTIFIER]
                for failed_row in self.failed_rows
            ):
                self.failed_rows.append(
                    (
                        benefit_id,
                        row[SMP_UNIQUE_IDENTIFIER],
                        "Reimbursement Category not found.",
                    )
                )
        return category

    def validate_cost_sharing_category(
        self, row: dict, global_procedure: Optional[GlobalProcedure] = None
    ) -> CostSharingCategory | None:
        benefit_id = self.get_benefit_id(row=row)
        cost_share_category = None
        if global_procedure:
            cost_sharing_category = global_procedure["cost_sharing_category"]
            if (
                cost_sharing_category
                and cost_sharing_category.upper() in CostSharingCategory.__members__
            ):
                cost_share_category = CostSharingCategory[cost_sharing_category.upper()]
            else:
                log.error(
                    f"{self.job_name}: Cost Sharing Category not found.",
                    global_procedure_id=global_procedure["id"],
                )
                if not any(
                    failed_row[1] == row[SMP_UNIQUE_IDENTIFIER]
                    for failed_row in self.failed_rows
                ):
                    self.failed_rows.append(
                        (
                            benefit_id,
                            row[SMP_UNIQUE_IDENTIFIER],
                            "Cost Sharing Category not found.",
                        )
                    )
        return cost_share_category

    def validate_wallet_balance(
        self,
        row: dict,
        wallet: ReimbursementWallet,
        direct_payment_category: ReimbursementRequestCategory,
    ) -> int | None:
        benefit_id = self.get_benefit_id(row=row)

        if self.enable_unlimited_benefits_for_smp:
            category_association = direct_payment_category.get_category_association(  # type: ignore[union-attr]
                reimbursement_wallet=wallet
            )
            balance: CategoryBalance = self.wallet_service.get_wallet_category_balance(
                wallet=wallet, category_association=category_association
            )
            wallet_balance = balance.current_balance
        else:
            wallet_balance_data = wallet.get_direct_payment_balances()
            wallet_balance = wallet_balance_data[1]

        if self.enable_unlimited_benefits_for_smp and balance.is_unlimited:
            log.info(
                f"{self.job_name}: Fetching wallet balance for unlimited benefit",
                wallet_id=str(wallet.id),
                category_id=str(direct_payment_category.id),
            )
            return balance.current_balance
        elif (not self.enable_unlimited_benefits_for_smp and not wallet_balance) or (
            self.enable_unlimited_benefits_for_smp and balance.current_balance <= 0
        ):
            log.error(
                f"{self.job_name}: There is no wallet balance remaining",
                wallet_id=str(wallet.id),
            )
            if not any(
                failed_row[1] == row[SMP_UNIQUE_IDENTIFIER]
                for failed_row in self.failed_rows
            ):
                self.failed_rows.append(
                    (
                        benefit_id,
                        row[SMP_UNIQUE_IDENTIFIER],
                        "No wallet balance remaining.",
                    )
                )

        return wallet_balance

    def get_pharmacy_prescription(self, row: dict) -> Optional[PharmacyPrescription]:
        return self.pharmacy_prescription_service.get_prescription_by_unique_id_status(
            rx_unique_id=row[SMP_UNIQUE_IDENTIFIER]
        )

    def get_valid_pharmacy_prescription_from_file(
        self, row: dict
    ) -> Optional[PharmacyPrescription]:
        """Checks for an existing Pharmacy Prescription that meets validation requirements"""
        benefit_id = self.get_benefit_id(row=row)
        existing_prescription = self.get_pharmacy_prescription(row=row)
        if not existing_prescription:
            log.error(
                "Could not find existing pharmacy prescription.",
                benefit_id=benefit_id,
                smp_unique_id=row[SMP_UNIQUE_IDENTIFIER],
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Missing Pharmacy Prescription.",
                )
            )
        elif existing_prescription.maven_benefit_id != benefit_id:
            log.error(
                f"{self.file_type} file benefit id does not matched existing prescription",
                existing_benefit_id=existing_prescription.maven_benefit_id,
                benefit_id=benefit_id,
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Benefit ID does not match existing prescription.",
                )
            )
            existing_prescription = None

        return existing_prescription

    def get_treatment_procedure(
        self, row: dict, prescription: PharmacyPrescription
    ) -> Optional[TreatmentProcedure]:
        benefit_id = self.get_benefit_id(row=row)
        treatment_procedure = TreatmentProcedure.query.get(
            prescription.treatment_procedure_id
        )
        if not treatment_procedure:
            log.error(
                "Did not find existing Treatment Procedure",
                benefit_id=benefit_id,
                smp_unique_id=row[SMP_UNIQUE_IDENTIFIER],
                prescription_id=prescription.id,
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Missing Treatment Procedure.",
                )
            )
            return None

        if treatment_procedure.status != TreatmentProcedureStatus.SCHEDULED:
            log.error(
                "Treatment Procedure not in allowed status to process.",
                benefit_id=benefit_id,
                smp_unique_id=row[SMP_UNIQUE_IDENTIFIER],
                prescription_id=prescription.id,
                treatment_procedure_status=treatment_procedure.status,
            )
            self.failed_rows.append(
                (
                    benefit_id,
                    row[SMP_UNIQUE_IDENTIFIER],
                    "Treatment Procedure not in a processable status.",
                )
            )
            treatment_procedure = None

        return treatment_procedure

    def create_pharmacy_prescription(
        self, row: dict, prescription_params: dict, user_id: Optional[int] = None
    ) -> PharmacyPrescription:
        """Creates and stores a Pharmacy Prescription record"""
        shared_fields = {
            "rx_unique_id": row[SMP_UNIQUE_IDENTIFIER],
            "ncpdp_number": row[SMP_NCPDP_NUMBER],
            "ndc_number": row[SMP_NDC_NUMBER],
            "rx_name": row[SMP_DRUG_NAME],
            "rx_description": row[SMP_DRUG_DESCRIPTION],
            "rx_first_name": row[SMP_FIRST_NAME],
            "rx_last_name": row[SMP_LAST_NAME],
            "rx_order_id": row[SMP_RX_ORDER_ID],
            "rx_received_date": datetime.datetime.strptime(
                row[SMP_RX_RECEIVED_DATE], "%m/%d/%Y"
            ),
            "user_id": user_id,
        }
        # Merge the dictionaries
        combined_values = {**shared_fields, **prescription_params}
        # Create the PharmacyPrescription object
        new_pharmacy_prescription = PharmacyPrescription(**combined_values)
        return self.pharmacy_prescription_service.create_pharmacy_prescription(
            instance=new_pharmacy_prescription
        )

    def update_pharmacy_prescription(
        self, prescription: PharmacyPrescription, prescription_params: dict
    ) -> PharmacyPrescription:
        """Updates a given Pharmacy Prescription record"""
        for key, value in prescription_params.items():
            setattr(prescription, key, value)
        return self.pharmacy_prescription_service.update_pharmacy_prescription(
            instance=prescription
        )

    @staticmethod
    def get_default_category(
        wallet: ReimbursementWallet,
    ) -> ReimbursementRequestCategory | None:
        """Returns a Reimbursement Category associated with the wallet"""
        all_categories = wallet.get_or_create_wallet_allowed_categories
        return (
            all_categories[0].reimbursement_request_category if all_categories else None
        )


def process_smp_file(
    processor: Any, input_date: Optional[datetime.date] = None
) -> bool:
    """
    Retrieve and process file from either GCS or SFTP based on feature flag.
    """
    log.info("Start file ingestion.", file_type=processor.file_type)
    try:
        file_prefix = processor.get_file_prefix()

        if feature_flags.bool_variation(
            ENABLE_SMP_GCS_BUCKET_PROCESSING, default=False
        ):
            try:
                pharmacy_handler = PharmacyFileHandler(
                    internal_bucket_name=SMP_GCP_BUCKET_NAME,
                    outgoing_bucket_name=QUATRIX_OUTBOUND_BUCKET,
                )
                log.info("Attempting file retrieval file from GCS.")
                file_content, filename = pharmacy_handler.get_pharmacy_ingestion_file(
                    file_prefix=file_prefix,
                    file_type=processor.file_type,
                    input_date=input_date,
                )

                if not file_content:
                    log.error(
                        f"{processor.job_name}: No {processor.file_type} file found in GCS."
                    )
                    return False

                ingestion_file = io.StringIO(file_content)
                log.info(
                    f"{processor.job_name}: Retrieved file from GCS.", filename=filename
                )

                valid_file = validate_file(ingestion_file)
                if not valid_file:
                    log.error(f"{processor.job_name}: Empty file returned!")
                    return False

                # Handle shipped file receipt
                if processor.file_type == "shipped":
                    pharmacy_handler.send_file_receipt(file_content, filename)  # type: ignore[arg-type]
                    ingestion_file.seek(0)

            except Exception as e:
                log.error(
                    f"{processor.job_name}: Unable to retrieve {processor.file_type} csv file!",
                    error=e,
                )
                return False
        else:
            ingestion_file = get_smp_ingestion_file(
                file_prefix, processor.file_type, input_date
            )
            if not ingestion_file:
                log.error(
                    f"{processor.job_name}: Unable to retrieve {processor.file_type} csv file from SFTP server!"
                )
                return False

            valid_file = validate_file(ingestion_file)
            if not valid_file:
                log.error(f"{processor.job_name}: Empty file returned!")
                return False

            if processor.file_type == "shipped":
                _send_file_receipt(ingestion_file)
                ingestion_file.seek(0)

        processor.process_file(ingestion_file)

    except Exception as e:
        log.error(
            f"{processor.job_name}: Exception encountered while processing {processor.file_type} file. Process failed.",
            error=e,
        )
        return False

    log.info(f"{processor.file_type} file processed successfully.")
    return True
