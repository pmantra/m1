from enum import Enum
from typing import List

from authn.models.user import User
from common import stats
from common.payments_gateway import PaymentsGatewayException, get_client
from common.stats import timed
from direct_payment.billing.constants import INTERNAL_TRUST_PAYMENT_GATEWAY_URL
from direct_payment.clinic.services.clinic import FertilityClinicService
from direct_payment.reconciliation.constants import (
    BILL_AMOUNT_FIELD_NAME,
    CLINIC_LOCATION_NAME_FIELD_NAME,
    CLINIC_RECONCILIATION_REPORT_GENERATION_ERROR_COUNT_METRIC_NAME,
    CLINIC_RECONCILIATION_REPORT_GENERATION_TIME_METRIC_NAME,
    PATIENT_DOB_FIELD_NAME,
    PATIENT_FIRST_NAME_FIELD_NAME,
    PATIENT_LAST_NAME_FIELD_NAME,
    PAYMENT_REFUND_SOURCE_TYPE,
    PROCEDURE_END_DATE_FIELD_NAME,
    PROCEDURE_NAME_FIELD_NAME,
    PROCEDURE_START_DATE_FIELD_NAME,
    REPORT_FIELDS,
    TREATMENT_PROCEDURE_SOURCE_TYPE,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from storage.connection import db
from utils.log import logger
from utils.payments import convert_cents_to_dollars

log = logger(__name__)


class FailureReason(Enum):
    FAILURE_IN_CREATING_REPORT = 1
    RECIPIENT_ID_NOT_FOUND = 2
    ERROR_IN_RETRIEVING_RECIPIENT_ID = 3
    ERROR_IN_PAYMENT_SERVICE = 4
    ERROR_IN_RETRIEVING_REPORT_DATA = 5


class ClinicReconciliationReportGenerator:
    def __init__(
        self,
        dry_run: bool,
        clinic_group_name: str,
        clinic_names: List[str],
        start_time: int,
        end_time: int,
    ):
        self.dry_run = dry_run
        self.clinic_group_name = clinic_group_name
        self.clinic_names = clinic_names
        self.start_time = start_time
        self.end_time = end_time
        self.clinic_service = FertilityClinicService(session=db.session)
        self.payment_gateway_client = get_client(INTERNAL_TRUST_PAYMENT_GATEWAY_URL)  # type: ignore[arg-type] # Argument 1 to "get_client" has incompatible type "Optional[str]"; expected "str"
        self.treatment_repo = TreatmentProcedureRepository()

    def generate_clinic_reconciliation_report(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        clinic_to_recipient_id_map = self._get_clinic_to_recipient_id_map()

        report_data_rows = []
        for clinic_name, recipient_id in clinic_to_recipient_id_map.items():
            try:
                paid_bills = (
                    self.payment_gateway_client.get_reconciliation_by_recipient(
                        recipient_id=recipient_id,
                        start_time=self.start_time,
                        end_time=self.end_time,
                    ).json()
                )
            except PaymentsGatewayException as e:
                log.error(
                    "Failed to retrieve paid bills",
                    recipient_id=recipient_id,
                    start_time=self.start_time,
                    end_time=self.end_time,
                    error=str(e),
                    exc_info=True,
                )
                self._increment_error_counter(FailureReason.ERROR_IN_PAYMENT_SERVICE)
                # Stop the job when there are issues during interacting with the payment service
                return [], False

            if not paid_bills:
                log.warn(
                    "No paid bills found",
                    recipient_id=recipient_id,
                    start_time=self.start_time,
                    end_time=self.end_time,
                )
                continue

            for paid_bill in paid_bills:
                log.info(
                    "Process paid bill",
                    source_type=paid_bill.get("source_type", ""),
                    recipient_id=recipient_id,
                    payout_id=paid_bill["stripe_payout_id"],
                    stripe_tx_id=paid_bill["stripe_transfer_id"],
                )
                if paid_bill.get("source_type", "") in [
                    TREATMENT_PROCEDURE_SOURCE_TYPE,
                    PAYMENT_REFUND_SOURCE_TYPE,
                ]:
                    treatment_procedure_id = paid_bill["source_id"]
                    payout_id = paid_bill["stripe_payout_id"]
                    stripe_tx_id = paid_bill["stripe_transfer_id"]
                    paid_amount = convert_cents_to_dollars(paid_bill["amount"])

                    try:
                        report_data = self._get_report_data(int(treatment_procedure_id))
                        report_data_rows.append(
                            [
                                report_data.get(PATIENT_FIRST_NAME_FIELD_NAME),
                                report_data.get(PATIENT_LAST_NAME_FIELD_NAME),
                                report_data.get(PATIENT_DOB_FIELD_NAME),
                                report_data.get(PROCEDURE_NAME_FIELD_NAME),
                                clinic_name,
                                report_data.get(CLINIC_LOCATION_NAME_FIELD_NAME),
                                stripe_tx_id,
                                payout_id,
                                report_data.get(PROCEDURE_START_DATE_FIELD_NAME),
                                report_data.get(PROCEDURE_END_DATE_FIELD_NAME),
                                "{:.2f}".format(  # type: ignore[str-format] # Incompatible types in string interpolation (expression has type "None", placeholder has type "Union[int, float]")
                                    report_data.get(BILL_AMOUNT_FIELD_NAME)
                                ),
                                f"{paid_amount:.2f}",
                            ]
                        )
                    except Exception as e:
                        # Exception when handling one paid bill won't stop the job
                        log.error(
                            "Error in retrieving report data",
                            treatment_procedure_id=treatment_procedure_id,
                            error=str(e),
                            exc_info=True,
                        )
                        self._increment_error_counter(
                            FailureReason.ERROR_IN_RETRIEVING_REPORT_DATA
                        )

        success = self._generate_csv_report(report_data_rows)
        if success:
            return report_data_rows, success
        return [], False

    def _get_clinic_to_recipient_id_map(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        recipient_id_map = {}
        for clinic_name in self.clinic_names:
            try:
                recipient_id = self.clinic_service.get_recipient_id_by_clinic_name(
                    clinic_name=clinic_name
                )
                if recipient_id:
                    log.info(
                        "Get a recipient id",
                        clinic_name=clinic_name,
                        recipient_id=recipient_id,
                    )
                    recipient_id_map[clinic_name] = recipient_id
                else:
                    log.error(
                        "recipient id is unavailable",
                        clinic_name=clinic_name,
                        clinic_group_name=self.clinic_group_name,
                    )
                    self._increment_error_counter(FailureReason.RECIPIENT_ID_NOT_FOUND)
            except Exception as e:
                log.error(
                    "Error in retrieving recipient id",
                    clinic_name=clinic_name,
                    clinic_group_name=self.clinic_group_name,
                    error=str(e),
                )
                self._increment_error_counter(
                    FailureReason.ERROR_IN_RETRIEVING_RECIPIENT_ID
                )
        return recipient_id_map

    def _get_report_data(
        self,
        treatment_procedure_id: int,
    ) -> dict:
        with timed(
            metric_name=CLINIC_RECONCILIATION_REPORT_GENERATION_TIME_METRIC_NAME,
            pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            tags=[f"clinic_group:{self.clinic_group_name}"],
        ):
            treatment_procedure = self.treatment_repo.read(
                treatment_procedure_id=treatment_procedure_id
            )

            billed_amount = convert_cents_to_dollars(treatment_procedure.cost)
            procedure_name = treatment_procedure.procedure_name
            procedure_start_date = treatment_procedure.start_date
            procedure_end_date = treatment_procedure.end_date
            clinic_location_name = (
                treatment_procedure.fertility_clinic_location.name
                if treatment_procedure.fertility_clinic_location is not None
                else ""
            )

            user = User.query.get(treatment_procedure.member_id)
            if not user:
                raise Exception(
                    f"No users found for treatment_procedure_id={treatment_procedure_id}"
                )
            patient_first_name = user.first_name
            patient_last_name = user.last_name
            patient_dob = ""
            if user.health_profile and user.health_profile.birthday:
                patient_dob = user.health_profile.birthday.strftime("%Y%m%d")

            return {
                PATIENT_FIRST_NAME_FIELD_NAME: patient_first_name,
                PATIENT_LAST_NAME_FIELD_NAME: patient_last_name,
                PATIENT_DOB_FIELD_NAME: patient_dob,
                PROCEDURE_NAME_FIELD_NAME: procedure_name,
                CLINIC_LOCATION_NAME_FIELD_NAME: clinic_location_name,
                PROCEDURE_START_DATE_FIELD_NAME: procedure_start_date,
                PROCEDURE_END_DATE_FIELD_NAME: procedure_end_date,
                BILL_AMOUNT_FIELD_NAME: billed_amount,
            }

    def _generate_csv_report(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        report_data_rows,
    ):
        if self.dry_run:
            log.info(
                "In dry run mode. Print the report data",
                clinic_group_name=self.clinic_group_name,
                start_time=self.start_time,
                end_time=self.end_time,
            )
            log.info(f"{REPORT_FIELDS}")
            for r in report_data_rows:
                log.info(f"{r}")
            return True

        # todo: Figure out where to save the report file

        return True

    def _increment_error_counter(self, failure_reason: FailureReason):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        stats.increment(
            metric_name=CLINIC_RECONCILIATION_REPORT_GENERATION_ERROR_COUNT_METRIC_NAME,
            tags=[
                f"reason:{failure_reason.name}",
                f"clinic_group:{self.clinic_group_name}",
            ],
            pod_name=stats.PodNames.PAYMENTS_PLATFORM,
        )
