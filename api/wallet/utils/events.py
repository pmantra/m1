from __future__ import annotations

from datetime import datetime, timezone

from direct_payment.pharmacy.tasks.libs.common import (
    wallet_reimbursement_state_rx_auto_approved_event,
)
from utils import braze_events
from utils.braze import send_user_wallet_attributes
from wallet.models.constants import (
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestState,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet import ReimbursementWallet


# IMPORTANT: The ERISA workflow is a contractual determination. Do not update the logic
# or test cases without consulting Legal.
def send_reimbursement_request_state_event(
    reimbursement_request: ReimbursementRequest,
) -> None:
    state = reimbursement_request.state
    if state == ReimbursementRequestState.REIMBURSED:
        braze_events.wallet_reimbursement_state_reimbursed(reimbursement_request.wallet)
    elif state == ReimbursementRequestState.APPROVED:
        if reimbursement_request.erisa_workflow and reimbursement_request.appeal_of:
            braze_events.wallet_reimbursement_state_appeal_approved_erisa(
                reimbursement_request.wallet
            )
        else:
            if (
                reimbursement_request.auto_processed
                != ReimbursementRequestAutoProcessing.RX
            ):
                braze_events.wallet_reimbursement_state_approved(
                    reimbursement_request.wallet
                )
            else:
                wallet_reimbursement_state_rx_auto_approved_event(
                    reimbursement_request.person_receiving_service_id
                )
    elif state == ReimbursementRequestState.DENIED:
        if reimbursement_request.erisa_workflow:
            if reimbursement_request.appeal_of:
                braze_events.wallet_reimbursement_state_appeal_declined_erisa(
                    reimbursement_request.wallet
                )
            else:
                braze_events.wallet_reimbursement_state_declined_erisa(
                    reimbursement_request.wallet
                )
        else:
            braze_events.wallet_reimbursement_state_declined(
                reimbursement_request.wallet
            )


def send_wallet_qualification_event(wallet: ReimbursementWallet) -> None:
    if wallet.get_direct_payment_category:
        resource = wallet.reimbursement_organization_settings.benefit_overview_resource
        event_data = {
            "program_overview_link": resource.custom_url
            if resource
            else ""  # resource is nullable in db
        }
        if wallet.is_shareable:
            braze_events.mmb_wallet_qualified_and_shareable(
                wallet,
                event_data,
            )
        else:
            braze_events.mmb_wallet_qualified_not_shareable(
                wallet,
                event_data,
            )
    else:
        braze_events.wallet_state_qualified(wallet)
    now_ = datetime.now(timezone.utc)
    for wallet_user in wallet.all_active_users:
        send_user_wallet_attributes(
            external_id=wallet_user.esp_id, wallet_qualification_datetime=now_
        )
