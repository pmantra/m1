from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, List, Optional

from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.pharmacy.tasks.libs.smp_reimbursement_file import (
    ReimbursementFileProcessor,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator.accumulation_mapping_service import AccumulationMappingService
from storage.connection import db
from utils import braze_events
from utils.log import logger
from wallet.config import use_alegeus_for_reimbursements
from wallet.models.constants import (
    AlegeusClaimStatus,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
)
from wallet.models.reimbursement import ReimbursementClaim
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory
from wallet.utils.alegeus.claims.create import (
    create_claim_in_alegeus,
    upload_claim_attachments_to_alegeus,
)
from wallet.utils.alegeus.claims.sync import WalletClaims, sync_pending_claims
from wallet.utils.alegeus.debit_cards.document_linking import (
    upload_card_transaction_attachments_to_alegeus,
)
from wallet.utils.events import send_reimbursement_request_state_event

if TYPE_CHECKING:
    from wallet.models.reimbursement import ReimbursementRequest
    from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)


def handle_reimbursement_request_state_change(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    reimbursement_request: ReimbursementRequest, old_state
) -> List[FlashMessage]:
    """
    After updating a Reimbursement Request state from 'NEW' to 'PENDING',
    trigger this to audit and send Claim to Alegeus.
    Additionally, upload all attachments (Invoices, Receipts) for the Claim to Alegeus.

    Upon a new state change, braze events should also be sent depending on
    if the Reimbursement Request has been set to PENDING, APPROVED or DENIED

    Currently, most of this code is used for creating and updating reimbursement request claims in admin.
    Debit card transactions will be processed in a similar way from admin updates, but will branch off here
    in order to preserve functionality of manual claims until a larger refactor.
    """
    wallet = reimbursement_request.wallet
    old_state = old_state and ReimbursementRequestState(old_state)
    new_state = reimbursement_request.state
    messages = []

    # Below code handles manual claims created in admin
    if (
        old_state == ReimbursementRequestState.NEW
        and new_state == ReimbursementRequestState.PENDING
    ):
        if use_alegeus_for_reimbursements():
            if (
                reimbursement_request.auto_processed
                != ReimbursementRequestAutoProcessing.RX
            ):
                if reimbursement_request.claims:
                    claim_ids = [claim.id for claim in reimbursement_request.claims]

                    wallet_to_claim = WalletClaims(
                        wallet=wallet,
                        claims=reimbursement_request.claims,
                    )
                    sync_pending_claims([wallet_to_claim])
                    db.session.expire(reimbursement_request)

                    for existing_claim_id in claim_ids:
                        claim_after_sync = ReimbursementClaim.query.get(
                            existing_claim_id
                        )

                        if not claim_after_sync:
                            # If the Claim is removed during the sync, ReimbursementRequestState is set back to NEW
                            # Setting state to Pending to continue submitting Claim to Alegeus
                            reimbursement_request.state = (
                                ReimbursementRequestState.PENDING
                            )
                            messages = handle_create_new_claim_in_alegeus(
                                wallet, reimbursement_request, messages
                            )

                        elif claim_after_sync.status in [
                            None,
                            AlegeusClaimStatus.NEEDS_RECEIPT.value,
                        ]:
                            messages.append(
                                FlashMessage(
                                    message="Claims have already been submitted to Alegeus for this Reimbursement Request",
                                    category=FlashMessageCategory.INFO,
                                )
                            )
                            messages.append(
                                FlashMessage(
                                    message="Attempting to upload attachments for this Reimbursement Request",
                                    category=FlashMessageCategory.INFO,
                                )
                            )
                            messages = handle_upload_attachments_in_alegeus(
                                wallet,
                                reimbursement_request,
                                claim_after_sync,
                                messages,
                            )

                else:
                    messages.append(
                        FlashMessage(
                            message="Attempting to submit new Claim in Alegeus for this Reimbursement Request",
                            category=FlashMessageCategory.INFO,
                        )
                    )
                    messages = handle_create_new_claim_in_alegeus(
                        wallet, reimbursement_request, messages
                    )
            else:
                if (
                    reimbursement_request.procedure_type
                    == TreatmentProcedureType.PHARMACY.value
                ):
                    messages = (
                        handle_rx_auto_processed_reimbursement_request_state_change(
                            reimbursement_request=reimbursement_request,
                        )
                    )
    else:
        send_reimbursement_request_state_event(reimbursement_request)

    return messages


def handle_reimbursement_request_card_transaction_state_change(
    reimbursement_wallet: ReimbursementWallet,
    reimbursement_request: ReimbursementRequest,
    old_state: Optional[ReimbursementRequestState],
) -> Optional[List[FlashMessage]]:
    # TODO: Handle admin Debit Card status transition triggers here as well
    # Do we need to sync this transaction before uploading?
    messages = []
    if reimbursement_request.state == ReimbursementRequestState.RECEIPT_SUBMITTED:
        # Upload all attachments if we transition into receipt submitted state
        messages = handle_upload_card_transaction_attachments_in_alegeus(
            reimbursement_wallet, reimbursement_request, old_state=old_state
        )
    return messages


def handle_rx_auto_processed_reimbursement_request_state_change(
    reimbursement_request: ReimbursementRequest,
) -> List[FlashMessage]:
    messages = []
    try:
        processor = ReimbursementFileProcessor()
        cost_breakdown: CostBreakdown = processor.auto_reimbursement_request_service.get_cost_breakdown_from_reimbursement_request(
            reimbursement_request_id=reimbursement_request.id
        )
        if cost_breakdown:
            returned_expense_type = processor.auto_reimbursement_request_service.return_category_expense_type(
                category=reimbursement_request.category
            )
            expense_type = (
                returned_expense_type or ReimbursementRequestExpenseTypes.FERTILITY
            )

            reimbursement_method = (
                processor.auto_reimbursement_request_service.get_reimbursement_method(
                    wallet=reimbursement_request.wallet,
                    expense_type=expense_type,
                )
            )
            messages = processor.auto_reimbursement_request_service.submit_auto_processed_request_to_alegeus(
                reimbursement_request=reimbursement_request,
                cost_breakdown=cost_breakdown,
                wallet=reimbursement_request.wallet,
                reimbursement_method=reimbursement_method,
            )
            # Accumulate if necessary
            ams = AccumulationMappingService(db.session)
            is_valid = ams.reimbursement_request_is_valid_for_accumulation(
                reimbursement_request
            )
            should_accumulate = processor.auto_reimbursement_request_service.should_accumulate_automated_rx_reimbursement_request(
                reimbursement_request, cost_breakdown
            )
            if should_accumulate and is_valid:
                try:
                    mapping = ams.create_valid_reimbursement_request_mapping(
                        reimbursement_request=reimbursement_request
                    )
                    db.session.add(mapping)
                    db.session.commit()
                    messages.append(
                        FlashMessage(
                            message="Auto processed reimbursement request accumulation mapping created",
                            category=FlashMessageCategory.INFO,
                        )
                    )
                except Exception as e:
                    log.error(
                        "Failed to create RX auto-processed accumulation treatment mapping.",
                        reimbursement_request_id=str(reimbursement_request.id),
                        error=str(e),
                    )
                    messages.append(
                        FlashMessage(
                            message="Failed to create an accumulation mapping record for this RX auto-processed "
                            "reimbursement request. Please manually create one",
                            category=FlashMessageCategory.ERROR,
                        )
                    )
        else:
            messages.append(
                FlashMessage(
                    message="An auto processed reimbursement request must be in the approved state"
                    "and have a Cost Breakdown saved.",
                    category=FlashMessageCategory.INFO,
                )
            )
            reset_request_state(reimbursement_request)
    except Exception as e:
        tb = traceback.format_exc()
        log.error(
            "Failed to submit auto processed claim to Alegeus via admin.",
            reimbursement_request_id=str(reimbursement_request.id),
            error_message=str(e),
            traceback=tb,
        )
        messages.append(
            FlashMessage(
                message=f"Auto-processed RX failed with error message: {str(e)}",
                category=FlashMessageCategory.ERROR,
            )
        )
        messages = log_unable_to_submit_claim_to_alegeus(messages, e, tb)
        reset_request_state(reimbursement_request)

    return messages


def handle_create_new_claim_in_alegeus(
    wallet: ReimbursementWallet,
    reimbursement_request: ReimbursementRequest,
    messages: list,
) -> Optional[List[FlashMessage]]:
    try:
        (
            success,
            messages,
            created_claim,
        ) = create_claim_in_alegeus(wallet, reimbursement_request, messages)

        if success:
            braze_events.alegeus_claim_submitted(wallet)

            messages = handle_upload_attachments_in_alegeus(
                wallet, reimbursement_request, created_claim, messages  # type: ignore[arg-type] # Argument 3 to "handle_upload_attachments_in_alegeus" has incompatible type "Optional[ReimbursementClaim]"; expected "ReimbursementClaim"
            )

        else:
            messages = log_unable_to_submit_claim_to_alegeus(messages, None)
            reset_request_state(reimbursement_request)

    except Exception as e:
        tb = traceback.format_exc()
        messages = log_unable_to_submit_claim_to_alegeus(messages, e, tb)
        reset_request_state(reimbursement_request)
    return messages


def handle_upload_attachments_in_alegeus(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    wallet: ReimbursementWallet,
    reimbursement_request: ReimbursementRequest,
    claim: ReimbursementClaim,
    messages: list,
):
    try:
        success, messages = upload_claim_attachments_to_alegeus(
            wallet,
            reimbursement_request,
            claim,
            messages,
        )

        if success:
            braze_events.alegeus_claim_attachments_submitted(wallet)
        else:
            messages = log_unable_to_upload_attachments(messages, None)
            reset_request_state(reimbursement_request)

    except Exception as e:
        tb = traceback.format_exc()
        messages = log_unable_to_upload_attachments(messages, e, tb)
        reset_request_state(reimbursement_request)
    return messages


def handle_upload_card_transaction_attachments_in_alegeus(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    wallet: ReimbursementWallet,
    reimbursement_request: ReimbursementRequest,
    old_state=None,
):
    """
    Admin wrapper for uploading card transactions to Alegeus. Handles any messages to be passed back to Admin UI
    """
    messages = []
    try:
        success = upload_card_transaction_attachments_to_alegeus(
            reimbursement_request,
        )

        if success:
            braze_events.alegeus_card_transaction_attachments_submitted(wallet)
        else:
            messages = log_unable_to_upload_attachments(messages, None)
            reset_request_state(reimbursement_request, state=old_state)
    except Exception as e:
        tb = traceback.format_exc()
        messages = log_unable_to_upload_attachments(messages, e, tb)
        reset_request_state(reimbursement_request, state=old_state)
    return messages


def log_unable_to_submit_claim_to_alegeus(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    messages: list, e: Optional[Exception], tb: str = None  # type: ignore[assignment] # Incompatible default for argument "tb" (default has type "None", argument has type "str")
):
    message = "Unable to submit claim to Alegeus, resetting State to 'NEW'"
    log.exception(message, error=e, traceback=tb)
    messages.append(FlashMessage(message=message, category=FlashMessageCategory.ERROR))
    return messages


def log_unable_to_upload_attachments(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    messages: list, e: Optional[Exception], tb: str = None  # type: ignore[assignment] # Incompatible default for argument "tb" (default has type "None", argument has type "str")
):
    message = "Unable to upload all attachments to Alegeus, resetting State to 'NEW'"
    log.exception(message, error=e, traceback=tb)
    messages.append(FlashMessage(message=message, category=FlashMessageCategory.ERROR))
    return messages


def reset_request_state(
    reimbursement_request: ReimbursementRequest,
    state: ReimbursementRequestState = ReimbursementRequestState.NEW,
) -> None:
    reimbursement_request.state = state
    db.session.add(reimbursement_request)
    db.session.commit()
