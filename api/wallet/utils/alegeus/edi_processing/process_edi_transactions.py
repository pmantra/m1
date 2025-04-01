from __future__ import annotations

import csv
import enum
from datetime import datetime, timedelta

from audit_log.utils import emit_audit_log_create, emit_audit_log_update
from common import stats
from storage.connection import db
from utils.braze_events import debit_card_mailed
from utils.log import logger
from wallet.models.constants import CardStatus, ReimbursementRequestState, WalletState
from wallet.models.reimbursement import ReimbursementTransaction
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_debit_card import (
    ReimbursementWalletDebitCard,
    map_alegeus_card_status_codes,
)
from wallet.utils.alegeus.debit_cards.transactions.process_user_transactions import (
    get_all_debit_card_transactions,
)
from wallet.utils.alegeus.edi_processing.common import (
    ERROR_CODE_MAPPING,
    AlegeusExportRecordTypes,
    create_temp_file,
    format_file_date,
    get_files_from_alegeus,
    get_versioned_file,
    map_edi_results_header,
)

log = logger(__name__)

metric_prefix = "api.wallet.utils.alegeus.edi_processing.process_edi_transactions"


class AlegeusTransactionCode(str, enum.Enum):
    AUPI = "AUPI"  # Transaction status code for an Insufficient Documentation transaction in Alegeus.


# Download files from Alegeus

EN_EK_RECORD_COUNTER = 0
EM_RECORD_COUNTER = 0


def download_and_process_alegeus_transactions_export(is_retry: bool = False) -> bool:
    """
    Function that downloads a response and export file from Alegeus. We parse and log if errors are found within the
    response file.  We parse and process the export file which contains data about all orgs card transactions.

    @param is_retry: A bool indicating if this is manual re-run of this method
    @return: A boolean indicating the success of the function
    """
    sftp, client = None, None
    processed_alegeus_employee_ids = set()
    if is_retry:
        file_format = get_versioned_file(download=True)
    else:
        date_now = format_file_date()
        file_format = f"MAVENIL{date_now}"

    export_file = f"{file_format}.exp"
    results_file = f"{file_format}.res"
    success = False
    try:
        client, sftp, files = get_files_from_alegeus()
        if results_file in files:
            results_temp = create_temp_file(results_file, sftp)
            _process_edi_response(results_temp)
        else:
            log.error(
                f"download_and_process_alegeus_transactions_export: No Alegeus EDI results file found for {results_file}. "
                "Review logs for error code."
            )
        if export_file in files:
            export_temp = create_temp_file(export_file, sftp)
            # Iterate over the temp file first to  check for insufficient transaction codes.
            for line in export_temp:
                try:
                    _process_insufficient_transactions(line)
                except Exception as e:
                    log.exception(
                        "_process_insufficient_transactions."
                        "Unable to process record.",
                        error=e,
                    )
            db.session.commit()
            export_temp.seek(0)

            for line in export_temp:
                try:
                    _process_alegeus_transactions(line, processed_alegeus_employee_ids)
                except Exception as e:
                    log.exception(
                        "_process_alegeus_transactions.Unable to process record.",
                        error=e,
                    )
            success = True
            log.info(
                f"download_and_process_alegeus_transactions_export: Total members updated - EN_EK {EN_EK_RECORD_COUNTER},"
                f" EM records updated {EM_RECORD_COUNTER}"
            )
        else:
            log.error(
                f"download_and_process_alegeus_transactions_export: No Alegeus EDI transactions file found for {export_file}. "
                "Review logs for error code."
            )
    except Exception as e:
        log.exception(
            f"download_and_process_alegeus_transactions_export: Failed Alegeus EDI transactions download for date {file_format}",
            error=e,
        )
    finally:
        if sftp:
            sftp.close()
            client.close()  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "close"
        return success  # noqa  B012  TODO:  return/continue/break inside finally blocks cause exceptions to be silenced. Exceptions should be silenced in except blocks. Control statements can be moved outside the finally block.


def _process_edi_response(file):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Checks the header of the response file downloaded from Alegeus to see if there were any errors reported
    and logs them.

    @param file: The response file downloaded from Alegeus
    """
    i = 0
    file.seek(0)
    processed_headers = {}
    for line in file:
        cleaned_line = line.decode("utf-8").strip()
        line_items = cleaned_line.split(",")
        if len(line_items) > 3:  # Check the header to see if there are any errors
            processed_headers = map_edi_results_header(line_items)
            if processed_headers.get("total_errors") == 0:
                log.info(
                    f"_process_edi_response: No errors found in {processed_headers.get('file_name')}"
                )
                break
        else:
            error_code = int(line_items[2])
            error_code_description = ERROR_CODE_MAPPING.get(error_code, "Unknown")
            log.error(
                f"_process_edi_response: Error found for file:{processed_headers.get('file_name')}. "
                f"Export request type:{list(AlegeusExportRecordTypes)[i].name}. "
                f"Alegeus EDI error code:{error_code} ({error_code_description})"
            )
            # Errors reported in the order the export file was requested. This allows us to keep the sequence for
            # logging.
            i += 1


def _process_alegeus_transactions(line: str, processed_alegeus_employee_id: set):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Cleans the line data, reads what type of file and sends it to the correct processor. Each
    type of file has its own header that has the number of records for that type (EN, EM, EK).

    @param line: A line item from the downloaded export file.
    @param processed_alegeus_employee_id: A set that holds the employee id of records already processed
    """
    cleaned_line = line.decode("utf-8").strip()  # type: ignore[attr-defined] # "str" has no attribute "decode"; maybe "encode"?
    line_items = cleaned_line.split(",")
    if len(line_items) == 2:
        log.info(
            f"process_alegeus_transactions: Processing {line_items[1]} transactions."
        )  # Log the number of transactions being processed.
    else:
        record_type = line_items[0]
        if record_type == AlegeusExportRecordTypes.EN.name:
            en_dict = map_en_records(line_items)
            _process_en_ek_record(
                en_dict,
                processed_alegeus_employee_id,
                AlegeusExportRecordTypes.EN,
            )
        elif record_type == AlegeusExportRecordTypes.EM.name:
            _process_em_record(cleaned_line)
        elif record_type == AlegeusExportRecordTypes.EK.name:
            ek_dict = map_ek_records(line_items)
            _process_en_ek_record(
                ek_dict, processed_alegeus_employee_id, AlegeusExportRecordTypes.EK
            )
        else:
            log.info(
                f"_process_alegeus_transactions: Record type not found: {record_type}"
            )


def _process_insufficient_transactions(line):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Processes line items that are in status type insufficient and updates the reimbursement request only. This is
    done because Alegeus does not give us any other options (pending comment and pending reason are the alt options when
    it does work via the API.)

    Updating the request first allows us to avoid overriding it via the API call with an additional check.

    @param line: A line item from the downloaded export file.
    """
    cleaned_line = line.decode("utf-8").strip()
    line_items = cleaned_line.split(",")
    if len(line_items) == 2:
        return

    record_type = line_items[0]
    if record_type == AlegeusExportRecordTypes.EN.name:
        transaction_dict = map_en_records(line_items)
    elif record_type == AlegeusExportRecordTypes.EK.name:
        transaction_dict = map_ek_records(line_items)
    else:
        return

    transaction_status = transaction_dict.get("transaction_status")
    if (
        transaction_status == AlegeusTransactionCode.AUPI.value
        and transaction_dict.get("card_proxy_number")
    ):
        transaction_key = transaction_dict.get("transaction_key")
        reimbursement_transaction = ReimbursementTransaction.query.filter_by(
            alegeus_transaction_key=transaction_key
        ).first()
        if reimbursement_transaction:
            reimbursement_request = reimbursement_transaction.reimbursement_request
            emit_audit_log_update(reimbursement_request)
            reimbursement_request.update_state(
                ReimbursementRequestState.INSUFFICIENT_RECEIPT
            )
            db.session.add(reimbursement_request)


def map_en_records(line: list):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Headers found in the MAVEN EN template within the Alegeus UI
    fieldnames = [
        "record_type",
        "settlement_sequence_number",
        "settlement_date",
        "tpa_id",
        "employer_id",
        "employee_id",
        "plan_id_design",
        "account_type_code",
        "plan_start_date",
        "plan_end_date",
        "amount",
        "date",
        "approval_code",
        "merchant_name",
        "merchant_id",
        "tracking_number",
        "notes",
        "manual_claim_number",
        "external_claim_number",
        "transaction_key",
        "transaction_code",
        "transaction_status_change_date",
        "transaction_status_change_user_id",
        "transaction_status",
        "check_trace_number",
        "reimbursement_date",
        "reimbursement_method",
        "card_proxy_number",
    ]
    if len(line) == len(fieldnames):
        return dict(zip(fieldnames, line))


def map_ek_records(line: list):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Headers found in the MAVEN EK template within the Alegeus UI
    fieldnames = [
        "record_type",
        "settlement_sequence_number",
        "tpa_id",
        "employer_id",
        "plan_id",
        "employee_id",
        "account_type_code",
        "plan_start_date",
        "plan_end_date",
        "account_number",
        "card_proxy_number",
        "merchant_name",
        "merchant_id",
        "merchant_category_codes",
        "original_merchant_category_code",
        "tracking_number",
        "original_transaction_amount",
        "amount",
        "transaction_amount_and_fee",
        "remaining_amount",
        "transaction_code",
        "transaction_status",
        "original_transaction_date",
        "transaction_date",
        "effective_date",
        "settlement_date",
        "transaction_status_change_date",
        "last_updated",
        "last_updated_time",
        "ineligible_amount",
        "transaction_key",
    ]
    if len(line) == len(fieldnames):
        return dict(zip(fieldnames, line))


def map_em_records(cleaned_line: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Headers found in the MAVEN EM template within the Alegeus UI
    line = list(csv.reader([cleaned_line], delimiter=",", quotechar='"'))[0]
    fieldnames = [
        "record_type",
        "tpa_id",
        "employer_id",
        "employee_id",
        "dependent_id",
        "card_effective_date",
        "card_expire_date",
        "last_updated",
        "last_updated_time",
        "card_proxy_number",
        "primary_card",
        "status_code",
        "status_code_reason",
        "shipping_address",
        "creation_date",
        "mailed_date",
        "issue_date",
        "activation_date",
        "shipment_tracking_number",
    ]
    if (
        len(line) == len(fieldnames) or len(line) == len(fieldnames) - 1
    ):  # Account for shipment_tracking_number being None (for most cases)
        return dict(zip(fieldnames, line))


def _process_en_ek_record(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    line_dict: dict,
    processed_records: set,
    record_type: AlegeusExportRecordTypes,
):
    """
    Query for associated wallet and calls the get_all_debit_card_transactions to process the users transactions.

    @param line_dict: A dictionary of mapped line items from the downloaded export file.
    @param processed_records: A set that holds the employee id of records already processed.
    @param record_type: The enum type of record returned from export file line item.
    """

    # skip if missing data or if not a card transaction
    if line_dict and line_dict.get("card_proxy_number"):
        employee_id = line_dict.get("employee_id")
        if employee_id and employee_id not in processed_records:
            try:
                wallet = (
                    ReimbursementWallet.query.filter_by(
                        alegeus_id=employee_id,
                        state=WalletState.QUALIFIED,
                    )
                    .order_by(ReimbursementWallet.id.desc())
                    .one_or_none()
                )
                if wallet:
                    get_all_debit_card_transactions(wallet, timeout=10)
                    processed_records.add(employee_id)
                    _count_en_ek_rows()
                else:
                    log.error(
                        f"_process_en_ek_record: Missing wallet for alegeus_id: {employee_id}"
                    )
            except Exception as e:
                log.exception(
                    f"_process_en_ek_record: Error processing record for alegeus_id: {employee_id}",
                    error=e,
                )


def _process_em_record(line: str) -> bool:
    def tag_successful(successful: bool, reason: str | None = None) -> None:
        metric_name = f"{metric_prefix}._process_em_record"
        if successful:
            tags = ["success:true"]
        else:
            tags = ["success:false", f"reason:{reason}"]
        stats.increment(
            metric_name=f"{metric_name}",
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    em_dict = map_em_records(line)
    if em_dict:
        employee_id = em_dict.get("employee_id")
        card_proxy = em_dict.get("card_proxy_number")

        try:
            debit_card = ReimbursementWalletDebitCard.query.filter_by(
                card_proxy_number=card_proxy
            ).one_or_none()
            card_status, card_status_reason = map_alegeus_card_status_codes(
                int(em_dict.get("status_code"))
            )
            # Only update if the card is not permanently inactive and the updating status is not new
            if (
                debit_card
                and debit_card.card_status != CardStatus.CLOSED
                and card_status != CardStatus.NEW
            ):
                emit_audit_log_update(debit_card)
                debit_card.update_status(
                    card_status, card_status_reason=card_status_reason
                )
                if em_dict.get("mailed_date") and not debit_card.shipped_date:
                    try:
                        debit_card.shipped_date = datetime.strptime(
                            em_dict.get("mailed_date"), "%Y%m%d"
                        ).date()
                    except ValueError:
                        log.error(
                            "_process_em_record: Unable to parse debit card mailed date for debit_card_id.",
                            debit_card=str(debit_card.id),
                        )
                if (
                    em_dict.get("shipment_tracking_number")
                    and not debit_card.shipping_tracking_number
                ):
                    debit_card.shipping_tracking_number = em_dict.get(
                        "shipment_tracking_number"
                    )
            elif not debit_card:
                wallet = (
                    ReimbursementWallet.query.filter_by(
                        alegeus_id=employee_id,
                        state=WalletState.QUALIFIED,
                    )
                    .order_by(ReimbursementWallet.id.desc())
                    .one_or_none()
                )

                if wallet:
                    debit_card = ReimbursementWalletDebitCard(
                        reimbursement_wallet_id=wallet.id,
                        card_proxy_number=em_dict.get("card_proxy_number"),
                        card_last_4_digits=em_dict.get("card_proxy_number")[-4:],
                        card_status=card_status,
                        card_status_reason=card_status_reason,
                    )
                    emit_audit_log_create(debit_card)
                    if em_dict.get("creation_date"):
                        try:
                            debit_card.created_date = datetime.strptime(
                                em_dict.get("creation_date"), "%Y%m%d"
                            ).date()
                        except ValueError:
                            log.error(
                                "_process_em_record: Unable to parse debit card creation date for wallet",
                                wallet_id=str(wallet.id),
                            )
                    if em_dict.get("issue_date"):
                        try:
                            debit_card.issued_date = datetime.strptime(
                                em_dict.get("issue_date"), "%Y%m%d"
                            ).date()
                        except ValueError:
                            log.error(
                                "_process_em_record: Unable to parse debit card issue date for wallet",
                                wallet_id=str(wallet.id),
                            )

                    # Set the current card on the wallet if it's the primary card
                    if em_dict.get("primary_card") == "1":
                        wallet.debit_card = debit_card
                        db.session.add(wallet)
                    # Trigger email for new debit card, check for recent creation
                    if debit_card.created_date and debit_card.created_date > (
                        datetime.today().date() - timedelta(days=3)
                    ):
                        debit_card_mailed(wallet)
                else:
                    log.error(
                        f"_process_em_record: Wallet not found for Alegeus_id: {employee_id}. "
                    )
                    tag_successful(successful=False, reason="wallet_not_found")
                    return False
            else:
                log.error(
                    f"_process_em_record: Record does not meet conditions to process: Alegeus_Id {employee_id}. "
                )
                tag_successful(successful=False, reason="conditions_not_met")
                return False

            db.session.add(debit_card)
            db.session.commit()
            tag_successful(True)
            _count_em_rows()
            return True

        except Exception as e:
            log.exception(
                "_process_em_record: Unable to process debit card updates",
                alegeus_id=employee_id,
                error=e,
            )
            tag_successful(successful=False, reason="unexpected_error")
    else:
        log.error(
            "_process_em_record: EDI EM record incorrectly formatted - cannot map fields."
        )
        tag_successful(successful=False, reason="cannot_map_fields")

    return False


def _count_en_ek_rows() -> None:
    global EN_EK_RECORD_COUNTER
    EN_EK_RECORD_COUNTER += 1


def _count_em_rows() -> None:
    global EM_RECORD_COUNTER
    EM_RECORD_COUNTER += 1
