from utils.log import logger

log = logger(__name__)


class ACTIONS:
    password_changed = "password_changed"
    password_reset = "password_reset"
    user_added = "user_added"
    login = "login"
    availability_removed = "availability_removed"
    gift_purchased = "gift_purchased"
    message_fee_collected = "message_fee_collected"
    message_credit_refunded = "message_credit_refunded"
    user_post_creation_complete = "user_post_creation_complete"
    user_post_creation_tagged = "user_post_creation_tagged"
    reassociate_user_org = "reassociate_user_org"
    change_wallet_status = "change_wallet_status"
    change_reimbursement_request_status = "change_reimbursement_request_status"
    agreement_accepted = "agreement_accepted"
    agreement_updated = "agreement_updated"


def audit(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    action_type: str, user_id: int = None, *, action_target_type: str = None, **data  # type: ignore[assignment] # Incompatible default for argument "user_id" (default has type "None", argument has type "int") #type: ignore[assignment] # Incompatible default for argument "action_target_type" (default has type "None", argument has type "str")
):
    log.info(
        "audit_log_events",
        audit_log_info={
            "user_id": user_id,
            "action_type": action_type,
            "action_target_type": action_target_type,
            "action_data": data,
        },
    )
