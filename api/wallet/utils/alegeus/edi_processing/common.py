from __future__ import annotations

import base64
import datetime
import enum
import json
import socket
import tempfile
import time
from typing import Tuple

import paramiko
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from models.enterprise import Organization
from utils.log import logger
from wallet.constants import (
    ALEGEUS_FTP_HOST,
    ALEGEUS_FTP_PASSWORD,
    ALEGEUS_FTP_USERNAME,
    ALEGEUS_PASSWORD_EDI,
)
from wallet.decorators import validate_plan
from wallet.models.reimbursement import ReimbursementPlan
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)

log = logger(__name__)

# Error codes we've seen from Alegeus' massive list (3,778 and counting)
ERROR_CODE_MAPPING = {
    0: "Success",
    14005: "Duplicate employer account.",
    14010: "Duplicate ACH account.",
    990527: "Bank Account can not be empty.",
    990529: "Bank Routing can not be empty.",
    990530: "Bank Routing number is invalid.",
    100064: "To Date Field cannot exceed today's date.",
    100516: "No export data found",
}


class AlegeusExportRecordTypes(enum.Enum):
    EN = "EN"
    EM = "EM"
    EK = "EK"

    @staticmethod
    def list():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return list(map(lambda record_type: record_type.name, AlegeusExportRecordTypes))


def ssh_connect(hostname, port=22, username=None, password=None, max_attempts=1):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """A wrapper for paramiko, returns a SSHClient after it connects."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh_connect_retry(
            client,
            hostname,
            port=port,
            username=username,
            password=password,
            max_attempts=max_attempts,
        )
    except TimeoutError as e:
        log.exception(
            f"SFTP Connection timed out, attempts={max_attempts}.",
            error=e,
        )
        raise e
    except (
        paramiko.AuthenticationException,
        paramiko.BadHostKeyException,
        paramiko.SSHException,
        socket.error,
    ) as e:
        client.close()
        log.exception("SFTP Connection Failed.", error=e)
        raise e
    return client


def ssh_connect_retry(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    client, hostname, port=22, username=None, password=None, max_attempts=1
):
    if max_attempts <= 0:
        log.exception("SFTP Connection Failed, retry exceeded max attempts.")
        raise TimeoutError
    else:
        try:
            client.connect(hostname, port=port, username=username, password=password)
            return client
        except (paramiko.SSHException, socket.error):
            return ssh_connect_retry(
                client,
                hostname,
                port=port,
                username=username,
                password=password,
                max_attempts=max_attempts - 1,
            )


def get_client_sftp():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        client = ssh_connect(
            ALEGEUS_FTP_HOST,
            username=ALEGEUS_FTP_USERNAME,
            password=ALEGEUS_FTP_PASSWORD,
            max_attempts=2,
        )
        sftp = client.open_sftp()
        return client, sftp
    except (
        paramiko.AuthenticationException,
        paramiko.BadHostKeyException,
        paramiko.SSHException,
        socket.error,
    ) as e:
        log.exception(
            "get_files_from_alegeus: Alegeus SFTP connection error.",
            error=e,
        )
        raise e


def create_temp_file(file, sftp):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    temp = tempfile.TemporaryFile()
    sftp.getfo(file, temp)
    temp.seek(0)
    return temp


def get_files_from_alegeus():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        client = ssh_connect(
            ALEGEUS_FTP_HOST,
            username=ALEGEUS_FTP_USERNAME,
            password=ALEGEUS_FTP_PASSWORD,
            max_attempts=2,
        )
        sftp = client.open_sftp()
        files = sftp.listdir()
        return client, sftp, files
    except (
        paramiko.AuthenticationException,
        paramiko.BadHostKeyException,
        paramiko.SSHException,
        socket.error,
    ) as e:
        log.exception(
            "get_files_from_alegeus: Alegeus SFTP connection error.",
            error=e,
        )
        raise e


def map_edi_results_header(line: list) -> dict:
    return {
        "file_type": line[0],
        "file_name": line[1],
        "date_processed": line[2],
        "number_of_records": int(line[3]),
        "total_errors": int(line[4]),
        "file_processed": bool(line[5]),
        "template_name": line[6],
    }


def format_file_date():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return datetime.datetime.now().strftime("%Y%m%d")
    # This should work out to be the same if we're running the
    # upload at night and the download in the morning considering UTC.


def validate_input_date(date):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        return date.strftime("%Y%m%d")
    except ValueError:
        raise ValueError("Value must be a datetime object.")


def get_versioned_file(download=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    sftp, client, files, = (
        None,
        None,
        None,
    )
    file_date = format_file_date()
    file_prefix = f"MAVENIL{file_date}"
    count = 0
    try:
        client, sftp, files = get_files_from_alegeus()
    except Exception as e:
        log.exception(
            "get_versioned_file: Exception setting versioned file name.", error=e
        )
        raise e
    finally:
        if sftp:
            sftp.close()
            client.close()  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "close"

    if files:
        for file in files:
            if file.startswith(file_prefix) and file.endswith(".res"):
                count += 1
        if download and count >= 2:
            return f"{file_prefix}_{count - 1}"
        if count > 0:
            return f"{file_prefix}_{count}"
    else:
        return file_prefix


def get_transaction_code_from_transaction_key(transaction_key):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Returns the first two digits from the transaction key found on each transaction.
    # 11 - Auth, 12 - Posted
    return transaction_key[:2]


def get_plans_from_org_settings(organization: Organization) -> set:
    org_settings = ReimbursementOrganizationSettings.query.filter_by(
        organization=organization
    ).all()
    plans = set()
    for org_setting in org_settings:
        allowed_categories = org_setting.allowed_reimbursement_categories
        for allowed_category in allowed_categories:
            request_category = allowed_category.reimbursement_request_category
            plan = request_category.reimbursement_plan
            if plan:
                plans.add(plan)

    return plans


def get_total_plan_count(organization_list: list) -> int:
    total_plans = 0
    for organization_id in organization_list:
        organization = Organization.query.filter_by(id=organization_id).one()
        plans = get_plans_from_org_settings(organization)
        total_plans += len(plans)
    return total_plans


@validate_plan
def validated_plan_items(plan: ReimbursementPlan) -> dict:
    reimbursement_account_type = plan.reimbursement_account_type
    alegeus_account_type = reimbursement_account_type.alegeus_account_type
    plan_items = {
        "plan_id": plan.alegeus_plan_id,
        "account_type": alegeus_account_type,
        "start_date": validate_input_date(plan.start_date),
        "end_date": validate_input_date(plan.end_date),
        "run_out_date": validate_input_date(
            (plan.end_date + datetime.timedelta(days=90))
        ),
        "default_plan_options": 61 if alegeus_account_type == "DTR" else 53,
        "plan_options": 142 if alegeus_account_type == "DTR" else 138,
        "custom_description": plan.alegeus_plan_id,
        "auto_renew": 0
        if validate_input_date(plan.end_date)
        == validate_input_date(datetime.date(2099, 12, 31))
        else 1,
        "hra_type": 2 if alegeus_account_type == "DTR" else "",
    }

    return plan_items


def format_filename_for_new_employer_config(
    organization_list: list, file_type: str
) -> str:
    if len(organization_list) == 1:
        return f"MAVEN_{file_type}_{organization_list[0]}.mbi"
    else:
        return (
            f"MAVEN_{file_type}_BULK_{datetime.datetime.now().strftime('%Y%m%d')}.mbi"
        )


def get_employer_config_latest_response_filename(
    files: list, file_prefix: str
) -> Tuple[str, int]:
    count = 0
    for file in files:
        if file.startswith(file_prefix) and file.endswith(".res"):
            count += 1
    filename = f"{file_prefix}_{count}" if count > 1 else file_prefix
    return filename, count


def check_file_availability(filename: str, sftp, client, max_attempts=20) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    """
    Checks the Alegeus SFTP file server for filename given. Retries for 5 minutes if not found.
    """
    while max_attempts > 0:
        try:
            files = sftp.listdir()
            if filename in files:
                return True
            else:
                max_attempts -= 1
                time.sleep(15)
        except (paramiko.SSHException, socket.error, TimeoutError) as e:
            log.exception(
                "check_file_availability Exception caught while waiting for file.",
                error=e,
                filename=filename,
            )
            client.close()
            return False

    return False


def set_encryption_password(salt: str, password: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt.encode(),
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password))


def encrypt_data(data: dict, key: bytes) -> bytes:
    message = json.dumps(data)
    f = Fernet(key)
    return f.encrypt(message.encode())


def decrypt_data(data: bytes, key: bytes) -> bytes:
    f = Fernet(key)
    return f.decrypt(data)


def encrypt_banking_data(org_id: str, data: dict) -> bytes:
    org = Organization.query.get(org_id)
    alegeus_employer_id = org.alegeus_employer_id
    password = ALEGEUS_PASSWORD_EDI
    key = set_encryption_password(alegeus_employer_id, password.encode())  # type: ignore[union-attr] # Item "None" of "Optional[str]" has no attribute "encode"
    return encrypt_data(data, key)


def decrypt_banking_data(org_id: str, data: bytes) -> dict:
    org = Organization.query.get(org_id)
    alegeus_employer_id = org.alegeus_employer_id
    password = ALEGEUS_PASSWORD_EDI
    key = set_encryption_password(alegeus_employer_id, password.encode())  # type: ignore[union-attr] # Item "None" of "Optional[str]" has no attribute "encode"
    encoded_banking_info = decrypt_data(data, key)
    data = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "bytes")
    del data
    return json.loads(encoded_banking_info)
