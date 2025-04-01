import csv
from datetime import datetime
from io import StringIO

import pytz
from maven import feature_flags

from authn.models.user import User
from common import stats
from common.payments_gateway import PaymentsGatewayException, get_client
from common.stats import timed
from direct_payment.clinic.services.clinic import FertilityClinicService
from direct_payment.pharmacy.constants import (
    ENABLE_SMP_GCS_BUCKET_PROCESSING,
    QUATRIX_OUTBOUND_BUCKET,
    SMP_FERTILITY_CLINIC_1,
    SMP_FERTILITY_CLINIC_2,
    SMP_FERTILITY_CLINIC_4,
    SMP_FERTILITY_CLINIC_5,
    SMP_FOLDER_NAME,
    SMP_FTP_PASSWORD,
    SMP_FTP_USERNAME,
    SMP_GCP_BUCKET_NAME,
    SMP_HOST,
    SMP_RECONCILIATION_FILE_PREFIX,
    SMP_RECONCILIATION_GET_DATA_FAILURE,
    SMP_RECONCILIATION_GET_DATA_TIME,
)
from direct_payment.pharmacy.pharmacy_prescription_service import (
    PharmacyPrescriptionService,
)
from direct_payment.pharmacy.tasks.libs.common import (
    UNAUTHENTICATED_PAYMENT_SERVICE_URL,
)
from direct_payment.pharmacy.tasks.libs.pharmacy_file_handler import PharmacyFileHandler
from storage.connection import db
from utils.log import logger
from utils.payments import convert_cents_to_dollars
from utils.sftp import SSHError, get_client_sftp

log = logger(__name__)


def get_results(start_time, end_time):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    with timed(
        metric_name=SMP_RECONCILIATION_GET_DATA_TIME,
        pod_name=stats.PodNames.PAYMENTS_PLATFORM,
        tags=[],
    ):
        payment_gateway_client = get_client(UNAUTHENTICATED_PAYMENT_SERVICE_URL)
        pharmacy_prescription_service = PharmacyPrescriptionService(session=db.session)
        clinic_service = FertilityClinicService(session=db.session)
        all_transfers = []
        recipient_ids = {
            clinic_service.get_recipient_id_by_clinic_name(clinic_name=name)
            for name in [
                SMP_FERTILITY_CLINIC_1,
                SMP_FERTILITY_CLINIC_2,
                SMP_FERTILITY_CLINIC_4,
                SMP_FERTILITY_CLINIC_5,
            ]
        }

        for recipient_id in recipient_ids:
            try:
                paid_bills = payment_gateway_client.get_reconciliation_by_recipient(
                    recipient_id=recipient_id,  # type: ignore[arg-type] # Argument "recipient_id" to "get_reconciliation_by_recipient" of "PaymentsGatewayClient" has incompatible type "Optional[str]"; expected "str"
                    start_time=start_time,
                    end_time=end_time,
                )

            except PaymentsGatewayException:
                log.error(
                    f"Failed to retrieve paid bills for recipient_id: {recipient_id}",
                    exc_info=True,
                )
                paid_bills = []
                stats.increment(
                    metric_name=SMP_RECONCILIATION_GET_DATA_FAILURE,
                    tags=["reason:PAYMENT_GATEWAY_EXCEPTION"],
                    pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                )

            if not paid_bills:
                stats.increment(
                    metric_name=SMP_RECONCILIATION_GET_DATA_FAILURE,
                    tags=["reason:NO_PAID_BILLS"],
                    pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                )
            all_transfers.extend(paid_bills.json())

        procedure_id_map = {
            int(bill["source_id"]): (bill["amount"], bill["stripe_transfer_id"])
            for bill in all_transfers
        }
        prescriptions = pharmacy_prescription_service.get_by_procedure_ids(
            list(procedure_id_map.keys())
        )
        if len(all_transfers) != len(procedure_id_map):
            stats.increment(
                metric_name=SMP_RECONCILIATION_GET_DATA_FAILURE,
                tags=["reason:INCOMPLETE_PROCEDURE_COUNT"],
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            )

        rows = []
        for prescription in prescriptions:
            member: User = User.query.get(prescription.user_id)
            first_name = member.first_name
            last_name = member.last_name
            date_of_birth = ""
            if member.health_profile and member.health_profile.birthday:
                date_of_birth = member.health_profile.birthday.strftime("%m%d%Y")
            else:
                stats.increment(
                    metric_name=SMP_RECONCILIATION_GET_DATA_FAILURE,
                    tags=["reason:NO_DATE_OF_BIRTH"],
                    pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                )
            rx_number = prescription.shipped_json.get("Rx #")
            if not rx_number:
                stats.increment(
                    metric_name=SMP_RECONCILIATION_GET_DATA_FAILURE,
                    tags=["reason:NO_RX_NUMBER"],
                    pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                )
            ncpdp_number = prescription.ncpdp_number
            rx_received_date = prescription.rx_received_date
            filled_date = prescription.actual_ship_date
            billed_amount = prescription.amount_owed
            paid_amount, auth_number = (
                procedure_id_map.get(prescription.treatment_procedure_id)[0],  # type: ignore[index] # Value of type "Optional[Tuple[Any, Any]]" is not indexable
                procedure_id_map.get(prescription.treatment_procedure_id)[1],  # type: ignore[index] # Value of type "Optional[Tuple[Any, Any]]" is not indexable
            )
            unique_id = prescription.rx_unique_id
            # reformat both billed_amount and paid_amount into dollar format
            paid_amount, billed_amount = convert_cents_to_dollars(
                paid_amount
            ), convert_cents_to_dollars(billed_amount)
            rows.append(
                [
                    first_name,
                    last_name,
                    date_of_birth,
                    rx_number,
                    auth_number,
                    ncpdp_number,
                    rx_received_date,
                    filled_date,
                    billed_amount,
                    paid_amount,
                    unique_id,
                ]
            )
        return rows


def generate_reconciliation_report(dry_run, start_time, end_time):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    rows = get_results(start_time, end_time)
    fields = [
        "First Name",
        "Last Name",
        "DOB",
        "Rx Number",
        "Auth Number",
        "NCPDP Number",
        "Rx Received Date",
        "Filled Date",
        "Billed Amount",
        "Paid Amount",
        "Unique Identifier",
    ]
    if dry_run:
        log.info("In dry run mode, report will be print out to stdout below")
        log.info(f"{fields}")
        for r in rows:
            log.info(f"{r}")
        return True

    now = datetime.now(pytz.timezone("America/New_York"))
    date_time = now.strftime("%Y%m%d_%H%M%S")
    file_name = f"{SMP_RECONCILIATION_FILE_PREFIX}_{date_time}.csv"
    buffer = StringIO()
    csvwriter = csv.writer(buffer, delimiter=",", quoting=csv.QUOTE_ALL)
    csvwriter.writerow(fields)
    csvwriter.writerows(rows)
    buffer.seek(0)

    if feature_flags.bool_variation(ENABLE_SMP_GCS_BUCKET_PROCESSING, default=False):
        pharmacy_handler = PharmacyFileHandler(
            internal_bucket_name=SMP_GCP_BUCKET_NAME,
            outgoing_bucket_name=QUATRIX_OUTBOUND_BUCKET,
        )
        return pharmacy_handler.upload_reconciliation_file(
            content=buffer, date_time_str=date_time
        )
    else:
        try:
            _, sftp_client = get_client_sftp(SMP_HOST, SMP_FTP_USERNAME, SMP_FTP_PASSWORD)  # type: ignore[arg-type] # Argument 2 to "get_client_sftp" has incompatible type "Optional[str]"; expected "str" #type: ignore[arg-type] # Argument 3 to "get_client_sftp" has incompatible type "Optional[str]"; expected "str"
            sftp_client.putfo(  # type: ignore[union-attr] # Item "None" of "Optional[SFTPClient]" has no attribute "putfo"
                buffer,  # type: ignore[arg-type] # Argument 1 to "putfo" of "SFTPClient" has incompatible type "StringIO"; expected "IO[bytes]"
                f"{SMP_FOLDER_NAME}/MavenGoldStripePayments/{file_name}",
                confirm=False,
            )
        except SSHError:
            log.error("Failed to ssh to the sftp server", exc_info=True)
            return False
        except Exception:
            log.error("Got exception during upload", exc_info=True)
            return False
        finally:
            sftp_client.close()  # type: ignore[union-attr] # Item "None" of "Optional[SFTPClient]" has no attribute "close"
            return True  # noqa  B012  TODO:  return/continue/break inside finally blocks cause exceptions to be silenced. Exceptions should be silenced in except blocks. Control statements can be moved outside the finally block.
