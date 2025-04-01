from __future__ import annotations

import collections
import datetime
import json
import os
import tempfile
import time
from typing import IO, Dict, List, Optional, Tuple

import paramiko
from google.cloud import storage
from google.cloud.exceptions import Conflict, GoogleCloudError
from google.cloud.storage import Bucket
from paramiko import SFTPError
from sqlalchemy.exc import DisconnectionError, OperationalError
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from app import create_app
from common import stats
from common.stats import timed
from direct_payment.pharmacy.constants import (
    DEFAULT_SCHEMA_PATH,
    ESI_BACKUP_FILENAME_PATTERN,
    ESI_BUCKET_NAME,
    ESI_DECRYPTION_SECRET,
    ESI_INGESTION_EXECUTION_TIME,
    ESI_INGESTION_FAILURE,
    ESI_INGESTION_SECRET,
    ESI_INGESTION_SUCCESS,
    ESI_OUTBOUND_DIR,
    ESI_OUTBOUND_FILENAME_PATTERN,
    ESI_PARSER_DR_RECORD_REJECTION,
    ESI_PARSER_EXECUTION_TIME,
    ESI_PARSER_FAILURE,
    ESI_PARSER_RECORD_CONVERTED,
    ESI_PARSER_RECORD_SAVED,
)
from direct_payment.pharmacy.health_plan_ytd_service import (
    HealthPlanYearToDateSpendService,
)
from direct_payment.pharmacy.ingestion_meta_service import IngestionMetaService
from direct_payment.pharmacy.models.health_plan_ytd_spend import (
    HealthPlanYearToDateSpend,
)
from direct_payment.pharmacy.models.ingestion_meta import (
    IngestionMeta,
    JobType,
    TaskStatus,
    TaskType,
)
from direct_payment.pharmacy.tasks.esi_parser import esi_converter
from direct_payment.pharmacy.tasks.esi_parser.esi_parser import ESIParser
from direct_payment.pharmacy.tasks.esi_parser.schema_extractor import FixedWidthSchema
from direct_payment.pharmacy.utils.pgp import DecryptionError, KeyImportError, decrypt
from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_accumulation_reporting import (  # noqa: F401
    PayerAccumulationReports,
)
from storage.connection import db
from tasks.queues import job
from utils.log import logger
from utils.sftp import SSHError, get_client_sftp

log = logger(__name__)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=60),
    retry=(retry_if_exception_type(IOError) | retry_if_exception_type(SFTPError)),
)
def _download(file: str, temp_file_name: str, sftp: paramiko.SFTPClient) -> str:
    log.info(f"Downloading {file} from sftp")
    sftp.get(file, temp_file_name)
    log.info(f"Finished downloading {file}")
    return temp_file_name


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=60),
    retry=(
        retry_if_exception_type(Conflict) | retry_if_exception_type(GoogleCloudError)
    ),
)
def _upload(local_file: str, remote_file: str, bucket: Bucket) -> None:
    log.info(f"Uploading {remote_file} to GCS: {bucket}")
    blob = bucket.blob(remote_file)
    blob.upload_from_filename(local_file)
    log.info(f"Finished uploading {remote_file} to GCS: {bucket}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=60),
    retry=(
        retry_if_exception_type(Conflict) | retry_if_exception_type(GoogleCloudError)
    ),
)
def _download_from_gcs(local_file: str, remote_file: str, bucket: Bucket):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info(f"Downloading {remote_file} from GCS: {bucket}")
    blob = bucket.blob(remote_file)
    blob.download_to_filename(local_file)
    log.info(f"Finished downloading {remote_file} from GCS: {bucket}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=60),
    retry=(
        retry_if_exception_type(OperationalError)
        | retry_if_exception_type(DisconnectionError)
        | retry_if_exception_type(TimeoutError)
    ),
)
def _save_to_db(
    service: HealthPlanYearToDateSpendService, records: List[HealthPlanYearToDateSpend]
) -> int:
    log.info(f"Batch writing {len(records)} to DB")
    affected_rows = service.batch_create(records, batch=50)
    log.info(f"Finished batch writing {affected_rows} to DB")
    return affected_rows


def _find_files_to_process(
    files: list[str], task_type: TaskType, target_date: int
) -> list[str]:
    result = []

    def check_date(date):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if TaskType.INCREMENTAL == task_type:
            return date > target_date
        elif TaskType.FIXUP == task_type:
            return date == target_date

    log.info(f"Total files on SFTP server: {len(files)}")
    for file in files:
        match = ESI_OUTBOUND_FILENAME_PATTERN.match(file)
        if match:
            date = int(match.group(1))
            if check_date(date):
                result.append((file, date))
    return [file for file, date in sorted(result, key=lambda x: x[1], reverse=True)]


def _process_file(file: str, sftp_client: paramiko.SFTPClient, bucket: Bucket) -> bool:
    with tempfile.NamedTemporaryFile() as temp:
        try:
            _download(f"{ESI_OUTBOUND_DIR}/{file}", temp.name, sftp_client)
            _upload(temp.name, f"raw/{file}", bucket)
            return True
        except (IOError, SFTPError):
            stats.increment(
                metric_name=ESI_INGESTION_FAILURE,
                tags=["reason:DOWNLOAD_FAILURE"],
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            )
            return False
        except RetryError:
            stats.increment(
                metric_name=ESI_INGESTION_FAILURE,
                tags=["reason:UPLOAD_FAILURE"],
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            )
            return False


def _process_files(
    files: list[str], sftp_client: paramiko.SFTPClient, bucket: Bucket
) -> dict[str, bool]:
    process_status = collections.defaultdict(bool)
    for file in files:
        status = _process_file(file, sftp_client, bucket)
        if status:
            process_status[file] = True
            stats.increment(
                metric_name=ESI_INGESTION_SUCCESS,
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            )
        else:
            log.warning(f"Error occurred during backup file {file}")
    return process_status


def _get_decrypted_path(raw_path: str) -> str:
    fname = raw_path.split("/")[-1].split(".")[0]
    return f"decrypted/{fname}.txt"


def _decrypt_and_backup(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    file_name: str,
    bucket: Bucket,
    passphrase: str,
    private_key: str,
    decrypted_file: IO[str],
    remote_file_path: str,
):
    with tempfile.NamedTemporaryFile() as encrypted:
        try:
            _download_from_gcs(encrypted.name, file_name, bucket)
        except RetryError:
            log.error(f"Failed to download from GCS for {file_name}", exc_info=True)
            stats.increment(
                metric_name=ESI_PARSER_FAILURE,
                tags=["reason:DOWNLOAD_FAILURE"],
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            )
            return False
        # decrypt
        try:
            decrypt(encrypted.name, decrypted_file.name, passphrase, private_key)
            # upload
            _upload(decrypted_file.name, remote_file_path, bucket)
            return True
        except (KeyImportError, DecryptionError, FileNotFoundError):
            log.error("Error during decrypt process", exc_info=True)
            stats.increment(
                metric_name=ESI_PARSER_FAILURE,
                tags=["reason:DECRYPT_FAILURE"],
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            )
            # Indicate failed
            return False
        except RetryError:
            log.error("Error during backup process", exc_info=True)
            stats.increment(
                metric_name=ESI_PARSER_FAILURE,
                tags=["reason:BACKUP_FAILURE"],
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            )
            return False


def _parse_and_store_to_db(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    service: HealthPlanYearToDateSpendService,
    file_name: str,
    schema_file_path: str,
    remote_file_path: str,
):
    try:
        esi_parser = ESIParser(schema_file_path or DEFAULT_SCHEMA_PATH)
        records = esi_parser.parse(file_name)
        return _convert_and_store(service, records, remote_file_path)
    except FileNotFoundError:
        log.exception("Error during create esi_parser and parsing files")
        return False
    except Exception:
        log.exception("Error during batch save records to DB")
        return False


def _convert_and_store(
    service: HealthPlanYearToDateSpendService,
    records: List[Dict[FixedWidthSchema, Tuple]],
    remote_file_path: str,
) -> Tuple[bool, dict[str, int]]:
    results = []
    process_stats = collections.defaultdict(int)
    process_stats["total"] = len(records)
    stats.increment(
        metric_name=ESI_PARSER_RECORD_SAVED,
        tags=[f"expected:{remote_file_path}"],
        metric_value=len(records),
        pod_name=stats.PodNames.PAYMENTS_PLATFORM,
    )
    for record in records:
        try:
            intermediate = esi_converter.convert(record)
            is_dr_record, reason = esi_converter.check_record_status(intermediate)
            if is_dr_record:
                process_stats["dr_count"] += 1
                if reason:
                    transmission_id_from_esi_record = intermediate.transmission_id
                    response_status_from_esi_record = (
                        intermediate.transaction_response_status
                    )
                    reject_code_from_esi_record = intermediate.reject_code

                    is_valid_rejection_to_update = (
                        response_status_from_esi_record == "R"
                        and reject_code_from_esi_record != "793"
                        and transmission_id_from_esi_record != ""
                    )

                    context = dict(
                        accumulation_transaction_id=transmission_id_from_esi_record,
                        reject_code=reject_code_from_esi_record,
                        response_status=response_status_from_esi_record,
                    )
                    if is_valid_rejection_to_update:
                        try:
                            acc_treatment_mapping = (
                                db.session.query(AccumulationTreatmentMapping)
                                .filter(
                                    AccumulationTreatmentMapping.accumulation_unique_id
                                    == transmission_id_from_esi_record  # The unique ID for an ESI mapping is the transmission_id
                                )
                                .one_or_none()
                            )
                            if acc_treatment_mapping:
                                acc_treatment_mapping.treatment_accumulation_status = (
                                    TreatmentAccumulationStatus.REJECTED
                                )
                                db.session.add(acc_treatment_mapping)
                                db.session.commit()
                            else:
                                process_stats["dr_missing_tm_count"] += 1
                                log.error(
                                    "AccumulationTreatmentMapping not found with associated accumulation_transaction_id.",
                                    **context,
                                )
                        except Exception as e:
                            log.exception(
                                "Error occurred while updating treatment accumulation status to 'REJECTED'.",
                                error=e,
                                **context,
                            )
                            db.session.rollback()
                    else:
                        log.info("Not a valid ESI rejection to update.")
                    process_stats["dr_reject_count"] += 1
                    stats.increment(
                        metric_name=ESI_PARSER_DR_RECORD_REJECTION,
                        tags=[
                            f"reason:{reason}:{intermediate.sender_reference_number}"
                        ],
                        pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                    )
                else:
                    stats.increment(
                        metric_name=ESI_PARSER_RECORD_CONVERTED,
                        tags=["type:dr_record"],
                        pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                    )
                    # We want to store DR record if there's no error code
                    results.append(
                        esi_converter.convert_to_health_plan_ytd_spend(
                            intermediate, remote_file_path, is_dr_record=True
                        )
                    )
            # Skip DR record
            if not is_dr_record:
                process_stats["dq_count"] += 1
                stats.increment(
                    metric_name=ESI_PARSER_RECORD_CONVERTED,
                    tags=["type:dq_record"],
                    pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                )
                results.append(
                    esi_converter.convert_to_health_plan_ytd_spend(
                        intermediate, remote_file_path
                    )
                )
        except (TypeError, UnicodeDecodeError):
            log.error("Parse failure", exc_info=True)
            process_stats["parse_failure"] += 1
            stats.increment(
                metric_name=ESI_PARSER_FAILURE,
                tags=["reason:RAW_PARSE_FAILURE"],
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            )
        except ValueError:
            log.error("Convert failure", exc_info=True)
            process_stats["convert_failure"] += 1
            stats.increment(
                metric_name=ESI_PARSER_FAILURE,
                tags=["reason:RECORD_GEN_FAILURE"],
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            )
        except Exception:
            log.error("Unexpected failure", exc_info=True)
            process_stats["unexpected_failure"] += 1
            stats.increment(
                metric_name=ESI_PARSER_FAILURE,
                tags=["reason:UNKNOWN"],
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            )
    # If there's no converted HealthPlanYTD after the loop, something goes wrong
    if not results:
        return False, process_stats
    try:
        number_of_rows = _save_to_db(service, results)
        stats.increment(
            metric_name=ESI_PARSER_RECORD_SAVED,
            tags=[f"actual:{remote_file_path}"],
            metric_value=number_of_rows,
            pod_name=stats.PodNames.PAYMENTS_PLATFORM,
        )
        process_stats["saved_to_db"] += number_of_rows
    except RetryError:
        stats.increment(
            metric_name=ESI_PARSER_FAILURE,
            tags=["reason:DB_WRITES_FAILURE"],
            pod_name=stats.PodNames.PAYMENTS_PLATFORM,
        )
        return False, process_stats
    return True, process_stats


def _get_decrypt_secrets(secrets: str) -> Tuple[str, str]:
    """
    Recover the origin private key based on GSM secret

    The value stored in GSM is key.replace("\n", "\\n")
    this function reverse that

    Args:
        secrets: Secrets stored in GSM

    Returns: normalized private key

    """
    secrets_dict = json.loads(secrets)
    passphrase, private_key = secrets_dict.get("passphrase"), secrets_dict.get("key")
    private_key = private_key.replace("\\n", "\n")
    return passphrase, private_key


def _get_sftp_credential(credential_str: str) -> Tuple[str, str, str]:
    credential_dict = json.loads(credential_str)
    return (
        credential_dict.get("url"),
        credential_dict.get("username"),
        credential_dict.get("password"),
    )


@job(service_ns="pharmacy", team_ns="payments_platform")
def raw_mirror(task_type: TaskType, fixup_filename: Optional[str] = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    RQ job does mirror files (encrypted) from ESI SFTP server to Maven GCS

    The way to figure out which file Maven should ingest rely on metadata generated per run: *task*
    For each job run, the first thing it does is to find out the last succeeded task, based on the
    `most_recent_raw` filename, compare with what's on SFTP server and eventually located a list of files
    Maven haven't processed, then upload these files to Maven ESI bucket with prefix `raw/`

    Fixup is a mode useful when Maven noticed issue with the origin raw file, require re-run of the process
    then, a valid filename is expected from user as input.

    Args:
        task_type: Represent task is incremental or fixup
        fixup_filename:  Optional, only exists when task_type is fixup

    Returns:
    """
    with timed(
        metric_name=ESI_INGESTION_EXECUTION_TIME,
        pod_name=stats.PodNames.PAYMENTS_PLATFORM,
        tags=[],
    ):

        raw_mirror_task = IngestionMeta(
            task_id=None,
            task_started_at=datetime.datetime.utcnow(),  # type: ignore[arg-type] # Argument "task_started_at" to "IngestionMeta" has incompatible type "datetime"; expected "int"
            task_updated_at=None,
            task_type=task_type,
            task_status=TaskStatus.INPROGRESS,
            job_type=JobType.INGESTION,
            most_recent_raw=None,
            most_recent_parsed=None,
            max_tries=0,
            duration_in_secs=0,
            target_file=None,
        )
        meta_service = IngestionMetaService(session=db.session)
        client = storage.Client()
        bucket = client.get_bucket(os.environ.get(ESI_BUCKET_NAME))
        try:
            start_time = time.monotonic()
            most_recent_task = meta_service.get_most_recent_task(
                status=TaskStatus.SUCCESS,
                task_type=task_type,
                job_type=JobType.INGESTION,
            )
            host, username, password = _get_sftp_credential(
                os.environ.get(ESI_INGESTION_SECRET)  # type: ignore[arg-type] # Argument 1 to "_get_sftp_credential" has incompatible type "Optional[str]"; expected "str"
            )
            _, sftp_client = get_client_sftp(host, username, password)
            files = sftp_client.listdir(ESI_OUTBOUND_DIR)  # type: ignore[union-attr] # Item "None" of "Optional[SFTPClient]" has no attribute "listdir"
            if TaskType.INCREMENTAL == task_type:
                if most_recent_task:
                    log.info(f"Getting most recent task: {most_recent_task}")
                    last_processed_date = int(
                        ESI_BACKUP_FILENAME_PATTERN.match(  # type: ignore[union-attr] # Item "None" of "Optional[Match[str]]" has no attribute "group"
                            most_recent_task.most_recent_raw
                        ).group(
                            1
                        )
                    )
                else:
                    log.warning("No recent success task found, creating new one")
                    # We could use 19700101 as the oldest timestamp, but it's not really necessary since
                    # we just want to basically process all the files we have not seen.
                    # the file from ESI will stay no longer than 30 days
                    last_processed_date = 20231001
            elif TaskType.FIXUP == task_type:
                if not fixup_filename or not ESI_OUTBOUND_FILENAME_PATTERN.match(
                    fixup_filename
                ):
                    raise ValueError(
                        "Fixup mode needs a valid fixup filename to proceed"
                    )
                raw_mirror_task.target_file = fixup_filename
                last_processed_date = int(
                    ESI_OUTBOUND_FILENAME_PATTERN.match(fixup_filename).group(1)  # type: ignore[union-attr] # Item "None" of "Optional[Match[str]]" has no attribute "group"
                )
            else:
                raise ValueError(f"Unsupported task_type: {task_type}")

            new_files = _find_files_to_process(files, task_type, last_processed_date)
            if not new_files:
                log.error("No new files found to be processed")
                stats.increment(
                    metric_name=ESI_INGESTION_FAILURE,
                    tags=["reason:NO_FILES"],
                    pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                )
                raw_mirror_task.task_status = TaskStatus.FAILED
                return

            log.info(
                f"Starting backing up: {len(new_files)} files since {last_processed_date}"
            )
            process_status = _process_files(new_files, sftp_client, bucket)  # type: ignore[arg-type] # Argument 2 to "_process_files" has incompatible type "Optional[SFTPClient]"; expected "SFTPClient"
            # GCS Bucket file format
            raw_mirror_task.most_recent_raw = f"raw/{new_files[0]}"
            raw_mirror_task.task_status = TaskStatus.SUCCESS
            duration = time.monotonic() - start_time
            log.info(
                f"Finished back up job in {duration: .2f} seconds, "
                f"Percentage of succeed back up: {(sum(1 for v in process_status.values() if v) / len(process_status)) * 100 : .2f}"
            )
        except SSHError:
            log.exception("Failed to establish SFTP connection with ESI server")
            raw_mirror_task.task_status = TaskStatus.FAILED
            stats.increment(
                metric_name=ESI_INGESTION_FAILURE,
                tags=["reason:SFTP_CONNECTION"],
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            )
        except Exception:
            log.exception("ESI Ingestion failed")
            raw_mirror_task.task_status = TaskStatus.FAILED
            stats.increment(
                metric_name=ESI_INGESTION_FAILURE,
                tags=["reason:MISCELLANEOUS"],
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            )
        finally:
            meta_service.update_task(
                task=raw_mirror_task,
                task_updated_at=datetime.datetime.utcnow(),  # type: ignore[arg-type] # Argument "task_updated_at" to "update_task" of "IngestionMetaService" has incompatible type "datetime"; expected "int"
            )
            sftp_client.close()  # type: ignore[union-attr] # Item "None" of "Optional[SFTPClient]" has no attribute "close"
            return raw_mirror_task  # noqa  B012  TODO:  return/continue/break inside finally blocks cause exceptions to be silenced. Exceptions should be silenced in except blocks. Control statements can be moved outside the finally block.


@job(service_ns="pharmacy", team_ns="payments_platform")
def parse_and_save(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    task_type: TaskType,
    file_name: str,
    schema_file_path: str = None,  # type: ignore[assignment] # Incompatible default for argument "schema_file_path" (default has type "None", argument has type "str")
    raw_task: Optional[IngestionMeta] = None,
):
    """
    RQ job decrypt files from Maven GCS and store ESI claims into Maven database for further cost breakdown usage

    This job also rely on Task to locate what files should be parsed and stored, then decrypted the file, backup into
    prefix `decrypted/` in GCS, convert each line into HealthPlanYTD record, eventually save to DB.

    Args:
        task_type: Represent task is incremental or fixup
        file_name: Raw file path, `raw/Maven_RxAccum_*_*.pgp`
        schema_file_path: ESI Schema Path, default to the one live under `esi_parser/esi_schema/`
        raw_task: Task, created by the upstream job: backup
    """
    app = create_app()
    with app.app_context():
        meta_service = IngestionMetaService(session=db.session)
        client = storage.Client()
        bucket = client.get_bucket(os.environ.get(ESI_BUCKET_NAME))
        parse_and_save_task = IngestionMeta(
            task_id=None,
            task_started_at=datetime.datetime.utcnow(),  # type: ignore[arg-type] # Argument "task_started_at" to "IngestionMeta" has incompatible type "datetime"; expected "int"
            task_updated_at=None,
            task_type=task_type,
            task_status=TaskStatus.INPROGRESS,
            job_type=JobType.PARSER,
            most_recent_raw=file_name,
            most_recent_parsed=None,
            max_tries=0,
            duration_in_secs=0,
            target_file=None,
        )
        # If task exists, meaning job is triggered via normal ingestion flow
        if TaskType.INCREMENTAL == task_type:
            if raw_task:
                file_name = raw_task.most_recent_raw  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[str]", variable has type "str")
        elif TaskType.FIXUP == task_type:
            if not file_name or not ESI_BACKUP_FILENAME_PATTERN.match(file_name):
                raise ValueError("Fixup mode needs a valid fixup filename to proceed")
            parse_and_save_task.target_file = file_name
        service = HealthPlanYearToDateSpendService(session=db.session)
        decrypt_file_path = _get_decrypted_path(file_name)
        passphrase, private_key = _get_decrypt_secrets(
            os.environ.get(ESI_DECRYPTION_SECRET)  # type: ignore[arg-type] # Argument 1 to "_get_decrypt_secrets" has incompatible type "Optional[str]"; expected "str"
        )
        with timed(
            metric_name=ESI_PARSER_EXECUTION_TIME,
            pod_name=stats.PodNames.PAYMENTS_PLATFORM,
        ):
            # context manager for decrypted content to power decryption and parse process
            with tempfile.NamedTemporaryFile() as decrypted_file:
                # Decrypt file and backup
                try:
                    decrypt_backup_status = _decrypt_and_backup(
                        file_name,
                        bucket,
                        passphrase,
                        private_key,
                        decrypted_file,  # type: ignore[arg-type] # Argument 5 to "_decrypt_and_backup" has incompatible type "_TemporaryFileWrapper[bytes]"; expected "IO[str]"
                        decrypt_file_path,
                    )
                    if decrypt_backup_status:
                        # Convert to HealthPlanYTD and persist to DB
                        parse_and_store_status, process_stats = _parse_and_store_to_db(
                            service,
                            decrypted_file.name,
                            schema_file_path,  # type: ignore[arg-type] # Argument 3 to "_parse_and_store_to_db" has incompatible type "Optional[str]"; expected "str"
                            decrypt_file_path,
                        )
                        if parse_and_store_status:
                            parse_and_save_task.task_status = TaskStatus.SUCCESS
                            parse_and_save_task.most_recent_parsed = decrypt_file_path
                        else:
                            parse_and_save_task.task_status = TaskStatus.FAILED
                        log.info(f"Process stats: {process_stats}")
                    else:
                        log.error(
                            "Failure happened during decryption and backup process"
                        )
                        parse_and_save_task.task_status = TaskStatus.FAILED
                except Exception:
                    log.exception(
                        f"Error occurred during decrypt and parse process for: {file_name}"
                    )
                    parse_and_save_task.task_status = TaskStatus.FAILED
                finally:
                    meta_service.update_task(
                        task=parse_and_save_task,
                        task_updated_at=datetime.datetime.utcnow(),  # type: ignore[arg-type] # Argument "task_updated_at" to "update_task" of "IngestionMetaService" has incompatible type "datetime"; expected "int"
                    )
                    return parse_and_save_task  # noqa  B012  TODO:  return/continue/break inside finally blocks cause exceptions to be silenced. Exceptions should be silenced in except blocks. Control statements can be moved outside the finally block.


@job(service_ns="pharmacy", team_ns="payments_platform")
def ingest(
    job_type: JobType = None,  # type: ignore[assignment] # Incompatible default for argument "job_type" (default has type "None", argument has type "JobType")
    task_type: TaskType = None,  # type: ignore[assignment] # Incompatible default for argument "task_type" (default has type "None", argument has type "TaskType")
    fixup_file: Optional[str] = None,
) -> None:
    """
    Ingest is the RQ cron job
    """
    app = create_app()
    with app.app_context():
        # Retrieve from remote sftp server, back up to GCP blob storage
        if task_type:
            task_type = TaskType(task_type)
        else:
            task_type = TaskType.INCREMENTAL
        if task_type == TaskType.FIXUP and job_type:
            job_type = JobType(job_type) or JobType.INGESTION
            if job_type == JobType.INGESTION:
                return raw_mirror(task_type=task_type, fixup_filename=fixup_file)
            elif job_type == JobType.PARSER:
                return parse_and_save(
                    task_type=task_type, file_name=fixup_file, raw_task=None
                )
        else:
            raw_task = raw_mirror(task_type=task_type, fixup_filename=fixup_file)
            if raw_task.task_status == TaskStatus.SUCCESS:
                parse_and_save.delay(
                    task_type=task_type,
                    file_name=fixup_file,
                    raw_task=raw_task,
                    team_ns=stats.PodNames.PAYMENTS_PLATFORM,
                )
            else:
                log.error("Raw backup failed, skip parse process")
