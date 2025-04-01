from __future__ import annotations

import csv
import datetime
import io
import os
import tempfile
from typing import IO, Any, List, Optional

import pytz
from paramiko.sftp_client import SFTPClient

from authn.models.user import User
from braze import BrazeClient, BrazeEvent
from common.constants import current_web_origin
from common.global_procedures.constants import UNAUTHENTICATED_PROCEDURE_SERVICE_URL
from common.global_procedures.procedure import GlobalProcedure, ProcedureService
from direct_payment.pharmacy.constants import (
    RX_GP_HCPCS_CODE,
    SMP_FOLDER_NAME,
    SMP_FTP_PASSWORD,
    SMP_FTP_USERNAME,
    SMP_HOST,
    SMP_INGEST_FOLDER_NAME,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from storage.connection import db
from utils.log import logger
from utils.sftp import ssh_connect
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)

IS_INTEGRATIONS_K8S_CLUSTER = (
    True if os.environ.get("IS_INTEGRATIONS_K8S_CLUSTER") == "true" else False
)
UNAUTHENTICATED_PAYMENT_SERVICE_URL = f"{current_web_origin()}/api/v1/_/payments/"


def list_filenames_today(ftp: SFTPClient, path: str, prefix: str) -> List[str]:
    filenames = set(ftp.listdir(path))
    return [filename for filename in filenames if filename.startswith(prefix)]


def get_most_recent_file(files: list[str]) -> str | None:
    most_recent_file = None
    most_recent_timestamp = 0
    for file in files:
        parts = file.split("_")
        timestamp_str = parts[-1].split(".")[0]
        timestamp = int(timestamp_str)
        if timestamp > most_recent_timestamp:
            most_recent_file = file
            most_recent_timestamp = timestamp
    return most_recent_file


def create_temp_file(file_path: str, ftp: SFTPClient) -> tempfile.NamedTemporaryFile:  # type: ignore[valid-type] # Function "tempfile.NamedTemporaryFile" is not valid as a type
    temp = tempfile.NamedTemporaryFile()
    ftp.getfo(file_path, temp)
    temp.seek(0)
    return temp


def get_smp_ingestion_file(
    file_prefix: str, file_type: str, input_date: Optional[datetime.date] = None
) -> Any:
    """Given a file_prefix return a temporary file from the SMP SFTP server"""
    if input_date:
        date_time = input_date.strftime("%Y%m%d")
    else:
        date_time = datetime.datetime.now(pytz.timezone("America/New_York")).strftime(
            "%Y%m%d"
        )

    file_format = f"{file_prefix}_{date_time}"

    ssh_client = ssh_connect(
        hostname=SMP_HOST,
        username=SMP_FTP_USERNAME,  # type: ignore[arg-type] # Argument "username" to "ssh_connect" has incompatible type "Optional[str]"; expected "str"
        password=SMP_FTP_PASSWORD,  # type: ignore[arg-type] # Argument "password" to "ssh_connect" has incompatible type "Optional[str]"; expected "str"
        max_attempts=3,
    )
    ftp = None
    try:
        ftp = ssh_client.open_sftp()
        files = list_filenames_today(
            ftp=ftp,
            path=SMP_INGEST_FOLDER_NAME,
            prefix=file_format,
        )
        if not files:
            log.error(
                f"Today's {file_type} file not available in SMP server! Cancelling job...",
                files=files,
            )
            return None

        found_file = get_most_recent_file(files)
        temp_file = create_temp_file(f"{SMP_INGEST_FOLDER_NAME}/{found_file}", ftp)
        temp_file.name = found_file  # type: ignore[attr-defined] # tempfile.NamedTemporaryFile? has no attribute "name"
    except Exception as e:
        log.exception("Exception retrieving SMP files from SFTP server.", error=e)
        raise e
    finally:
        if ftp:
            ftp.close()
        ssh_client.close()
    return temp_file


def validate_file(file: io.StringIO | io.BytesIO) -> bool:
    """
    Validates that a file is not empty.
    """
    if not file:
        return False

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    return size > 0


def _send_file_receipt(received_file: tempfile.NamedTemporaryFile) -> None:  # type: ignore[valid-type] # Function "tempfile.NamedTemporaryFile" is not valid as a type
    log.info("Sending receipt file.")
    now = datetime.datetime.now(pytz.timezone("America/New_York"))
    date_time = now.strftime("%Y%m%d_%H%M%S")
    base_file_name, _ = os.path.splitext(received_file.name)  # type: ignore[attr-defined] # tempfile.NamedTemporaryFile? has no attribute "name"
    receipt_file_name = f"_Received_{date_time}.csv"

    ssh_client = ssh_connect(
        SMP_HOST, username=SMP_FTP_USERNAME, password=SMP_FTP_PASSWORD, max_attempts=3  # type: ignore[arg-type] # Argument "username" to "ssh_connect" has incompatible type "Optional[str]"; expected "str" #type: ignore[arg-type] # Argument "password" to "ssh_connect" has incompatible type "Optional[str]"; expected "str"
    )
    ftp = None
    try:
        ftp = ssh_client.open_sftp()
        existing_files = list_filenames_today(
            ftp=ftp,
            path=f"{SMP_FOLDER_NAME}/MavenAcknowledgement",
            prefix=base_file_name,
        )
        if not existing_files:
            ftp.putfo(
                received_file,
                f"{SMP_FOLDER_NAME}/MavenAcknowledgement/{base_file_name}{receipt_file_name}",
                confirm=False,
            )
            log.info("Receipt file uploaded successfully.", file=base_file_name)
    except Exception as e:
        log.error("Unable to upload receipt file to SMP SFTP server!", error=e)
    finally:
        if ftp:
            ftp.close()
        ssh_client.close()


def get_wallet_user(
    wallet: ReimbursementWallet, first_name: str, last_name: str
) -> User | None:
    wallet_user = None
    for member in wallet.all_active_users:
        if (
            f"{member.first_name.lower()} {member.last_name.lower()}"  # type: ignore[union-attr] # Item "None" of "Optional[str]" has no attribute "lower"
            == f"{first_name.lower()} {last_name.lower()}"
        ):
            wallet_user = member
    return wallet_user


def get_global_procedure(
    procedure_service_client: ProcedureService,
    rx_ndc_number: str,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> Optional[GlobalProcedure]:
    global_procedures = procedure_service_client.get_procedures_by_ndc_numbers(
        ndc_numbers=[rx_ndc_number],
        start_date=start_date,
        end_date=end_date,
    )
    if len(global_procedures) >= 1:
        for procedure in global_procedures:
            if procedure["type"] == "pharmacy":  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "type"
                return procedure  # type: ignore[return-value] # Incompatible return value type (got "Union[GlobalProcedure, PartialProcedure]", expected "Optional[GlobalProcedure]")
    return None


def create_rx_global_procedure(
    rx_procedure_name: str,
    rx_ndc_number: str,
    existing_procedure: GlobalProcedure,
    procedure_service_client: ProcedureService,
) -> GlobalProcedure:
    log.info(
        "Global Procedure not found. Creating a new procedure.",
        global_procedure_name=rx_procedure_name,
        global_procedure_ndc_number=rx_ndc_number,
    )
    global_procedure = GlobalProcedure(  # type: ignore[typeddict-item] # Missing keys ("id", "created_at", "updated_at", "partial_procedures") for TypedDict "GlobalProcedure"
        name=rx_procedure_name,
        type=existing_procedure["type"],
        credits=existing_procedure["credits"],
        ndc_number=rx_ndc_number,
        is_partial=False,
        hcpcs_code=RX_GP_HCPCS_CODE,
        annual_limit=existing_procedure["annual_limit"],
        is_diagnostic=existing_procedure["is_diagnostic"],
        cost_sharing_category=existing_procedure["cost_sharing_category"],
    )
    return procedure_service_client.create_global_procedure(  # type: ignore[return-value] # Incompatible return value type (got "Optional[GlobalProcedure]", expected "GlobalProcedure")
        global_procedure=global_procedure
    )


def get_or_create_rx_global_procedure(
    drug_name: str,
    ndc_number: str,
    treatment_procedure: TreatmentProcedure,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> Optional[GlobalProcedure]:
    if IS_INTEGRATIONS_K8S_CLUSTER:
        procedure_service_client = ProcedureService(
            base_url=UNAUTHENTICATED_PROCEDURE_SERVICE_URL
        )
    else:
        procedure_service_client = ProcedureService(internal=True)
    global_procedure = get_global_procedure(
        procedure_service_client=procedure_service_client,
        rx_ndc_number=ndc_number,
        start_date=start_date,
        end_date=end_date,
    )
    # An existing Global Procedure already exists with the updated ndc number.
    if global_procedure:
        log.info("Existing Global Procedure Found.")
        return global_procedure
    else:
        existing_procedure = procedure_service_client.get_procedure_by_id(
            procedure_id=treatment_procedure.global_procedure_id
        )
        if not existing_procedure:
            log.error(
                "Could not find existing Global Procedure record.",
                global_procedure_id=treatment_procedure.global_procedure_id,
                treatment_procedure_id=treatment_procedure.id,
            )
            return None
        new_global_procedure = create_rx_global_procedure(
            drug_name, ndc_number, existing_procedure, procedure_service_client  # type: ignore[arg-type] # Argument 3 to "create_rx_global_procedure" has incompatible type "Union[GlobalProcedure, PartialProcedure]"; expected "GlobalProcedure"
        )
        return new_global_procedure


def convert_to_string_io(file: IO[str] | IO[bytes]) -> io.StringIO:
    """
    Convert a file-like object to StringIO. Handles both text and binary files.
    """
    if not file:
        log.error("Empty file found.")
        raise ValueError("File cannot be empty!")

    try:
        file.seek(0)
        content = file.read()

        # Convert bytes to string if needed
        if isinstance(content, bytes):
            content = content.decode("utf-8")

        result = io.StringIO(str(content))
        result.seek(0)
        return result

    except Exception as e:
        log.error("Error converting file to StringIO.", error=e)
        raise ValueError("Error converting file to StringIO.") from e


def raw_rows_count(file: io.StringIO) -> int:
    """
    Returns the number of rows in a CSV file.
    """
    try:
        file.seek(0)
        reader = csv.reader(file)
        next(reader)  # Skip header row
        count = sum(1 for _ in reader)
        file.seek(0)
        return count
    except Exception as e:
        log.error("Error counting rows in file.", error=e)
        return 0


def wallet_reimbursement_state_rx_auto_approved_event(user_id: int) -> None:
    """
    Auto-processed approved RX prescriptions sends a Braze notification
    to inform the member of the approved RX Reimbursement Request.
    """
    log.info("Sending auto-processed approved notification to Braze")
    user = db.session.query(User).get(user_id)

    if not user:
        log.error(
            "Auto-processed RX User not found for Braze notification.", user_id=user_id
        )
        return

    braze_client = BrazeClient()
    braze_event = BrazeEvent(
        external_id=user.esp_id,
        name="wallet_reimbursement_state_rx_auto_approved",
    )
    braze_client.track_user(events=[braze_event])

    log.info(
        "Auto-Processed RX Prescription - Notified member of approved Reimbursement Request.",
        user_esp_id=user.esp_id,
        user_id=user.id,
    )
