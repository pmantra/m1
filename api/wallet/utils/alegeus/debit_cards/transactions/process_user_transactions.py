from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple

from audit_log.utils import emit_bulk_audit_log_update, get_flask_admin_user
from common import stats
from storage.connection import db
from utils.log import logger
from utils.payments import convert_dollars_to_cents
from wallet import alegeus_api
from wallet.alegeus_api import format_date_from_string_to_datetime
from wallet.models.constants import (
    AlegeusTransactionStatus,
    ReimbursementRequestState,
    ReimbursementRequestType,
    TaxationState,
)
from wallet.models.currency import Money
from wallet.models.reimbursement import (
    ReimbursementPlan,
    ReimbursementRequest,
    ReimbursementTransaction,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.services.currency import DEFAULT_CURRENCY_CODE, CurrencyService
from wallet.utils.alegeus.edi_processing.common import (
    get_transaction_code_from_transaction_key,
)

MAX_CALL_TIMES = 3

log = logger(__name__)


class AlegeusTransactionType(enum.Enum):
    MANUAL_CLAIM = "MANUAL CLAIM"
    CARD_TRANSACTION = "CARD TRANSACTION"


class AlegeusAuthType(enum.Enum):
    CARD_POST = "12"
    CARD_AUTH = "11"


transaction_adjudicated_states = [
    AlegeusTransactionStatus.APPROVED.value,
    AlegeusTransactionStatus.REFUNDED.value,
    AlegeusTransactionStatus.RESOLVED_NO_REFUND.value,
    AlegeusTransactionStatus.RESOLVED_PAYROLL.value,
    AlegeusTransactionStatus.INELIGIBLE_EXPENSE.value,
]


MAVEN_DEFAULT_LABEL = "Maven Card Transaction"

metric_prefix = "api.wallet.utils.alegeus.edi_processing.process_user_transactions"


def get_all_debit_card_transactions(
    wallet: ReimbursementWallet, timeout: int = 2
) -> bool:
    """
    Function for calling the Alegeus API to get all transaction activity for a specific member and then processes
    the response.

    @param wallet: The member's ReimbursementWallet
    @param timeout: The api timeout value when requesting all transactions from Alegeus
    @return: A boolean indicating that the response was successful
    """

    def tag_successful(
        successful: bool,
        reason: str | None = None,
        end_point: str | None = None,
    ) -> None:
        metric_name = f"{metric_prefix}.get_all_debit_card_transactions"
        tags = []
        if successful:
            tags.append("success:true")
        else:
            tags.append("success:false")
            tags.append(f"reason:{reason}")
            tags.append(f"end_point:{end_point}")

        stats.increment(
            metric_name=f"{metric_name}",
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    if wallet.debit_card:

        api = alegeus_api.AlegeusApi()
        call_times = 0
        while call_times < MAX_CALL_TIMES:
            try:
                all_transactions_response = api.get_employee_activity(wallet, timeout)

                if (
                    alegeus_api.is_request_successful(all_transactions_response)
                    and all_transactions_response.json() is not None
                ):

                    transaction_details = all_transactions_response.json()
                    process_transactions(transaction_details, wallet)
                    tag_successful(successful=True)
                    return True
                else:
                    if call_times < MAX_CALL_TIMES:
                        call_times += 1
                        continue
                    log.error(
                        "Unable to get_all_debit_card_transactions for wallet. Alegeus request failed.",
                        wallet_id=str(wallet.id),
                    )
                    tag_successful(
                        successful=False,
                        reason="alegeus_api_failure",
                        end_point="get_employee_activity",
                    )
                    return False

            except Exception as e:
                log.exception(
                    "Unable to get_all_debit_card_transactions for wallet.",
                    wallet_id=str(wallet.id),
                    error=e,
                )
                tag_successful(
                    successful=False,
                    reason="exception",
                    end_point="get_employee_activity",
                )
                return False
    return False


def get_transaction_details_from_alegeus(
    wallet: ReimbursementWallet, transactionid: str, seqnum: int, setldate: str
) -> Tuple[bool, list]:
    """
    Function for calling the Alegeus API to get transaction details for a specific member and transaction then processes
    the response.

    @param wallet: The member's ReimbursementWallet
    @param transactionid: The ID of the transaction to retrieve
    @param seqnum: The Sequential number assinged by the settlement system within a settlement date
    @param setldate: The date that the transactions were settled on.
    @return: A tuple with a boolean indicating the response was successful/failed and a json response
    """

    def tag_successful(successful: bool, reason: str | None = None) -> None:
        metric_name = f"{metric_prefix}.get_transaction_details_from_alegeus"
        tags = []
        if successful:
            tags.append("success:true")
        else:
            tags.append("success:false")
            tags.append(f"reason:{reason}")
        stats.increment(
            metric_name=f"{metric_name}",
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    api = alegeus_api.AlegeusApi()

    if wallet and transactionid and seqnum and setldate:
        try:
            transactions_details_response = api.get_transaction_details(
                wallet, transactionid, seqnum, setldate
            )

            if (
                alegeus_api.is_request_successful(transactions_details_response)
                and transactions_details_response.json() is not None
            ):
                tag_successful(successful=True)
                return True, transactions_details_response.json()
            else:
                log.error(
                    f"Unable to get_transaction_details_from_alegeus for transactionid {transactionid}."
                    "Alegeus request failed.",
                    wallet_id=str(wallet.id),
                )
                tag_successful(successful=False, reason="alegeus_request_failed")
                return False, None  # type: ignore[return-value] # Incompatible return value type (got "Tuple[bool, None]", expected "Tuple[bool, List[Any]]")
        except Exception as e:
            log.exception(
                f"Unable to get_transaction_details_from_alegeus for transactionid {transactionid} and wallet.",
                wallet_id=str(wallet.id),
                error=e,
            )
            tag_successful(successful=False, reason="unexpected_error")

    return False, None  # type: ignore[return-value] # Incompatible return value type (got "Tuple[bool, None]", expected "Tuple[bool, List[Any]]")


def process_transactions(
    transaction_details: list,
    wallet: ReimbursementWallet,
) -> None:
    """
    Function that process the response from the Alegeus API to get_employee_activity. This creates or updates
    reimbursement transactions and their associated reimbursement requests.

    @param transaction_details: List of all members account activity
    @param wallet: A members ReimbursementWallet
    """
    (
        all_transactions,
        transactions_and_requests_updated,
        transactions_and_requests_created,
    ) = (0, 0, 0)

    bulk_audit_log_update = []
    for transaction in transaction_details:
        transaction_type = transaction.get("Type")
        transaction_status = transaction.get("StatusCode")
        transaction_amount = transaction.get("Amount")
        transaction_key = transaction.get("TransactionKey")
        transaction_sequence_number = transaction.get("SeqNumber")
        # Make sure it's a card transaction or
        # a manual claim if amount is negative which is a refunded type.
        if (
            transaction_type == AlegeusTransactionType.CARD_TRANSACTION.value
            or transaction_type == AlegeusTransactionType.MANUAL_CLAIM.value
            and transaction_amount < 0
        ):
            transaction_code = get_transaction_code_from_transaction_key(
                transaction_key
            )
            if (
                transaction_code == AlegeusAuthType.CARD_AUTH.value
                and transaction_status != AlegeusTransactionStatus.FAILED.value
            ):
                continue

            all_transactions += 1
            try:
                with db.session.begin_nested():
                    transaction_activity_dict = create_response_dict_from_api(
                        transaction
                    )

                    reimbursement_transaction = (
                        ReimbursementTransaction.query.filter_by(
                            alegeus_transaction_key=transaction_key,
                            sequence_number=transaction_sequence_number,
                        ).one_or_none()
                    )

                    notes = None

                    if reimbursement_transaction:
                        bulk_audit_log_update.append(reimbursement_transaction)
                        # To avoid making unnecessary requests to get transaction details,
                        # perform a check when the transaction is moved into an adjudicated state
                        alegeus_transaction_status_code = transaction_activity_dict.get(
                            "transaction_status"
                        )
                        is_transaction_moved_to_adjudicated_state = (
                            int(reimbursement_transaction.status)
                            == AlegeusTransactionStatus.RECEIPT.value
                            and alegeus_transaction_status_code
                            in transaction_adjudicated_states
                        )
                        if is_transaction_moved_to_adjudicated_state:
                            notes = get_notes_from_alegeus_transaction_details(
                                wallet, transaction
                            )

                        reimbursement_transaction = update_reimbursement_transaction(
                            transaction_activity_dict, notes  # type: ignore[arg-type] # Argument 2 to "update_reimbursement_transaction" has incompatible type "Optional[Any]"; expected "str"
                        )
                        update_reimbursement_request(
                            reimbursement_transaction, transaction_activity_dict
                        )
                        transactions_and_requests_updated += 1
                    else:
                        if transaction_status in transaction_adjudicated_states:
                            notes = get_notes_from_alegeus_transaction_details(
                                wallet, transaction
                            )

                        reimbursement_request = create_reimbursement_request(
                            transaction_activity_dict, wallet, notes
                        )

                        if reimbursement_request:
                            create_reimbursement_transaction(
                                transaction_activity_dict, reimbursement_request, notes
                            )
                            transactions_and_requests_created += 1

            except Exception as e:
                log.exception(
                    "process_transactions: Unable to update_reimbursement_transaction or request",
                    wallet_id=str(wallet.id),
                    transaction_key=transaction_key,
                    sequence_number=transaction_sequence_number,
                    error=e,
                )

    if get_flask_admin_user():
        emit_bulk_audit_log_update(bulk_audit_log_update)
    db.session.commit()
    log.info(
        f"process_transactions. Total_Transactions:{all_transactions}, "
        f"Total_Created:{transactions_and_requests_created}, Total_Updated:{transactions_and_requests_updated}"
    )


def map_reimbursement_request_state_from_transaction_status(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    transaction_status: str,
    has_receipt: str,
    amount: float,
    display_status=None,
    old_state=None,
) -> ReimbursementRequestState:
    if transaction_status == AlegeusTransactionStatus.FAILED.value:
        return ReimbursementRequestState.FAILED

    if transaction_status == AlegeusTransactionStatus.APPROVED.value:
        if amount > 0:
            return ReimbursementRequestState.APPROVED
        else:
            return ReimbursementRequestState.REFUNDED

    if transaction_status == AlegeusTransactionStatus.INELIGIBLE_EXPENSE.value:
        return ReimbursementRequestState.INELIGIBLE_EXPENSE

    if transaction_status in [
        AlegeusTransactionStatus.RESOLVED_PAYROLL.value,
        AlegeusTransactionStatus.RESOLVED_NO_REFUND.value,
    ]:
        return ReimbursementRequestState.RESOLVED

    if transaction_status == AlegeusTransactionStatus.REFUNDED.value:
        return ReimbursementRequestState.REFUNDED

    if transaction_status == AlegeusTransactionStatus.RECEIPT.value:
        if not has_receipt:
            return ReimbursementRequestState.NEEDS_RECEIPT
        elif old_state == ReimbursementRequestState.INSUFFICIENT_RECEIPT:
            return ReimbursementRequestState.INSUFFICIENT_RECEIPT
        else:
            return ReimbursementRequestState.RECEIPT_SUBMITTED

    # We don't have the transaction status mapped.
    # Log the transaction status and set request to pending.
    log.warning(
        "Unknown API Transaction Status Code",
        transaction_status_code=transaction_status,
    )
    return ReimbursementRequestState.NEW


def create_response_dict_from_api(transaction_data: dict) -> dict:
    """
    Creates a dictionary of all the fields from the Alegeus API response needed to create
    a Reimbursement Transaction and the associated Reimbursement Request.

    @param transaction_data: A single dictionary item from he get_employee_activity response
    @return: A new mapped dictionary with keys that match our business logic.
    """
    try:
        card_transaction_details = transaction_data.get("CardTransactionDetails")
        merchant_name = MAVEN_DEFAULT_LABEL
        if card_transaction_details:
            merchant_name_dict = card_transaction_details.get("MerchantName")
            merchant_name = (
                merchant_name_dict if merchant_name_dict else MAVEN_DEFAULT_LABEL
            )

        transaction_dict = {
            "alegeus_transaction_key": transaction_data.get("TransactionKey"),
            "alegeus_plan_id": transaction_data.get("CustomDescription"),
            "date": format_date_from_string_to_datetime(transaction_data.get("Date")),  # type: ignore[arg-type] # Argument 1 to "format_date_from_string_to_datetime" has incompatible type "Optional[Any]"; expected "str"
            "amount": convert_dollars_to_cents(Decimal(transaction_data.get("Amount"))),  # type: ignore[arg-type] # Argument 1 to "Decimal" has incompatible type "Optional[Any]"; expected "Union[Decimal, float, str, Tuple[int, Sequence[int], int]]"
            "description": transaction_data.get("Description"),
            "service_start_date": format_date_from_string_to_datetime(
                transaction_data.get("ServiceStartDate")  # type: ignore[arg-type] # Argument 1 to "format_date_from_string_to_datetime" has incompatible type "Optional[Any]"; expected "str"
            ),
            "service_end_date": format_date_from_string_to_datetime(
                transaction_data.get("ServiceEndDate")  # type: ignore[arg-type] # Argument 1 to "format_date_from_string_to_datetime" has incompatible type "Optional[Any]"; expected "str"
            ),
            "settlement_date": datetime.strptime(
                transaction_data.get("SettlementDate"), "%Y%m%d"  # type: ignore[arg-type] # Argument 1 to "strptime" of "datetime" has incompatible type "Optional[Any]"; expected "str"
            ).date(),
            "sequence_number": transaction_data.get("SeqNumber"),
            "transaction_status": transaction_data.get("StatusCode"),
            "transaction_status_display": transaction_data.get("DisplayStatus"),
            "transaction_type": transaction_data.get("Type"),
            "transaction_account_type": transaction_data.get("AcctTypeCode"),
            "service_provider": merchant_name,
            "person_receiving_service": transaction_data.get("Claimant"),
            "has_receipt": transaction_data.get("HasReceipts"),
            "pended_comment": transaction_data.get("PendedComment"),
            "pended_reason": transaction_data.get("PendedReason"),
        }
    except AttributeError as e:
        log.exception(
            "create_response_dict_from_api: Missing transaction data.", error=e
        )
        raise e

    return transaction_dict


def create_reimbursement_transaction(
    transaction_activity_dict: dict,
    reimbursement_request: ReimbursementRequest,
    notes: Optional[str] = None,
) -> ReimbursementTransaction:
    """
    Creates a Reimbursement Transaction object. Amount field is stored in cents.

    @param transaction_activity_dict: A single card transaction response from Alegeus.
    @param reimbursement_request:  ReimbursementRequest
    @param notes: The notes field from alegeus transaction details response
    @return ReimbursementTransaction
    """

    reimbursement_transaction = ReimbursementTransaction(
        reimbursement_request=reimbursement_request,
        alegeus_transaction_key=transaction_activity_dict.get(
            "alegeus_transaction_key"
        ),
        alegeus_plan_id=transaction_activity_dict.get("alegeus_plan_id"),
        date=transaction_activity_dict.get("date"),
        amount=Decimal(transaction_activity_dict.get("amount")),  # type: ignore[arg-type] # Argument 1 to "Decimal" has incompatible type "Optional[Any]"; expected "Union[Decimal, float, str, Tuple[int, Sequence[int], int]]"
        description=transaction_activity_dict.get("description"),
        status=transaction_activity_dict.get("transaction_status"),
        service_start_date=transaction_activity_dict.get("service_start_date"),
        service_end_date=transaction_activity_dict.get("service_end_date"),
        settlement_date=transaction_activity_dict.get("settlement_date"),
        sequence_number=transaction_activity_dict.get("sequence_number"),
    )
    if notes:
        reimbursement_transaction.notes = notes

    db.session.add(reimbursement_transaction)

    return reimbursement_transaction


def create_reimbursement_request(
    transaction_activity_dict: dict,
    wallet: ReimbursementWallet,
    notes: Optional[str] = None,
) -> ReimbursementRequest:
    """
    Creates a ReimbursementRequest from a card transaction response.

    @param transaction_activity_dict: a dictionary formed out of the single transaction response.
    @param wallet: ReimbursementWallet
    @param notes: The notes field from alegeus transaction details response
    @return ReimbursementRequest
    """
    reimbursement_request = None
    alegeus_plan_id = transaction_activity_dict.get("alegeus_plan_id")
    reimbursement_plan = ReimbursementPlan.query.filter_by(
        alegeus_plan_id=alegeus_plan_id
    ).one_or_none()
    transaction_type = transaction_activity_dict.get("transaction_type")

    if reimbursement_plan:
        state = map_reimbursement_request_state_from_transaction_status(
            transaction_status=transaction_activity_dict.get("transaction_status"),  # type: ignore[arg-type] # Argument "transaction_status" to "map_reimbursement_request_state_from_transaction_status" has incompatible type "Optional[Any]"; expected "str"
            has_receipt=transaction_activity_dict.get("has_receipt"),  # type: ignore[arg-type] # Argument "has_receipt" to "map_reimbursement_request_state_from_transaction_status" has incompatible type "Optional[Any]"; expected "str"
            amount=transaction_activity_dict.get("amount"),  # type: ignore[arg-type] # Argument "amount" to "map_reimbursement_request_state_from_transaction_status" has incompatible type "Optional[Any]"; expected "float"
            display_status=transaction_activity_dict.get("display_status"),
        )
        reimbursement_request = ReimbursementRequest(
            label=transaction_activity_dict.get("service_provider"),
            category=reimbursement_plan.category,
            reimbursement_request_category_id=reimbursement_plan.category.id,
            service_provider=transaction_activity_dict.get("service_provider"),
            amount=transaction_activity_dict.get("amount"),
            reimbursement_wallet_id=wallet.id,
            wallet=wallet,
            service_start_date=transaction_activity_dict.get("service_start_date"),
            reimbursement_type=ReimbursementRequestType.DEBIT_CARD,
            person_receiving_service=transaction_activity_dict.get(
                "person_receiving_service"
            ),
        )

        # Populate currency-specific related amount columns
        currency_service = CurrencyService()
        transaction: Money = currency_service.to_money(
            amount=reimbursement_request.amount, currency_code=DEFAULT_CURRENCY_CODE
        )
        currency_service.process_reimbursement_request(
            transaction=transaction, request=reimbursement_request
        )

        # Set these only if defined, otherwise use defaults
        is_prepaid, taxation_status = compute_prepayment_and_taxation(
            transaction_type, notes  # type: ignore[arg-type] # Argument 1 to "compute_prepayment_and_taxation" has incompatible type "Optional[Any]"; expected "str" #type: ignore[arg-type] # Argument 2 to "compute_prepayment_and_taxation" has incompatible type "Optional[str]"; expected "str"
        )
        if is_prepaid is not None:
            reimbursement_request.is_prepaid = is_prepaid
        if taxation_status is not None:
            reimbursement_request.taxation_status = taxation_status

        db.session.add(reimbursement_request)
        reimbursement_request.update_state(state, transaction_activity_dict)

    else:
        log.error(
            "create_reimbursement_request: Unable to get the ReimbursementPlan for wallet.",
            wallet_id=str(wallet.id),
        )
    return reimbursement_request  # type: ignore[return-value] # Incompatible return value type (got "Optional[TimeLoggedSnowflakeModelBase]", expected "ReimbursementRequest")


def update_reimbursement_transaction(
    transaction_activity_dict: dict, notes: str
) -> ReimbursementTransaction:
    """
    Looks for existing ReimbursementTransaction in db.  If found, update the current status.

    @param transaction_activity_dict: A dictionary formed out of the single transaction response
    @param notes: The notes field from alegeus transaction details response
    @return: ReimbursementTransaction
    """
    transaction_key = transaction_activity_dict.get("alegeus_transaction_key")
    sequence_number = transaction_activity_dict.get("sequence_number")
    reimbursement_transaction = ReimbursementTransaction.query.filter_by(
        alegeus_transaction_key=transaction_key, sequence_number=sequence_number
    ).one()
    reimbursement_transaction.status = transaction_activity_dict.get(
        "transaction_status"
    )
    # Notes are only pulled when transaction becomes adjudicated. Avoid clearing previous note otherwise.
    if notes:
        reimbursement_transaction.notes = notes

    db.session.add(reimbursement_transaction)

    return reimbursement_transaction


def update_reimbursement_request(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    reimbursement_transaction: ReimbursementTransaction, transaction_activity_dict: dict
):
    """
    Given a ReimbursementTransaction object update the associated ReimbursementRequests status.

    @param reimbursement_transaction: A Reimbursement Transaction
    @param transaction_activity_dict: A dictionary of a single debit card transaction
    """
    transaction_type = transaction_activity_dict.get("transaction_type")
    reimbursement_request = reimbursement_transaction.reimbursement_request
    state = map_reimbursement_request_state_from_transaction_status(
        transaction_status=reimbursement_transaction.status,  # type: ignore[arg-type] # Argument "transaction_status" to "map_reimbursement_request_state_from_transaction_status" has incompatible type "Optional[str]"; expected "str"
        has_receipt=transaction_activity_dict.get("has_receipt"),  # type: ignore[arg-type] # Argument "has_receipt" to "map_reimbursement_request_state_from_transaction_status" has incompatible type "Optional[Any]"; expected "str"
        amount=transaction_activity_dict.get("amount"),  # type: ignore[arg-type] # Argument "amount" to "map_reimbursement_request_state_from_transaction_status" has incompatible type "Optional[Any]"; expected "float"
        display_status=transaction_activity_dict.get("display_status"),
        old_state=reimbursement_request.state,
    )

    # Set these only if defined, do not clear existing
    is_prepaid, taxation_status = compute_prepayment_and_taxation(
        transaction_type, reimbursement_transaction.notes  # type: ignore[arg-type] # Argument 1 to "compute_prepayment_and_taxation" has incompatible type "Optional[Any]"; expected "str" #type: ignore[arg-type] # Argument 2 to "compute_prepayment_and_taxation" has incompatible type "Optional[str]"; expected "str"
    )
    if is_prepaid is not None:
        reimbursement_request.is_prepaid = is_prepaid
    if taxation_status is not None:
        reimbursement_request.taxation_status = taxation_status

    db.session.add(reimbursement_request)
    reimbursement_request.update_state(state, transaction_activity_dict)
    return reimbursement_request


def compute_prepayment_and_taxation(transaction_type: str, notes: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    is_prepaid = None
    taxation_status = None

    if (
        notes
        and "pre" in notes.lower()
        and transaction_type == AlegeusTransactionType.CARD_TRANSACTION.value
    ):
        is_prepaid = True
        taxation_status = TaxationState.TAXABLE

    return [is_prepaid, taxation_status]


def get_notes_from_alegeus_transaction_details(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    wallet: ReimbursementWallet, transaction
):
    transaction_key = transaction.get("TransactionKey")
    sequence_number = transaction.get("SeqNumber")
    settlement_date = transaction.get("SettlementDate")

    was_successful, transactions_details = get_transaction_details_from_alegeus(
        wallet, transaction_key, sequence_number, settlement_date
    )
    if was_successful and transactions_details and transactions_details.get("Notes"):  # type: ignore[attr-defined] # "List[Any]" has no attribute "get"
        return transactions_details.get("Notes")  # type: ignore[attr-defined] # "List[Any]" has no attribute "get"

    return None
