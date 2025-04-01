from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Mapping

from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from common.payments_gateway import PaymentGatewayEventMessage
from direct_payment.billing.errors import BillingServicePGMessageProcessingError
from direct_payment.notification.errors import PaymentGatewayMessageProcessingError
from direct_payment.notification.lib.tasks.rq_send_notification import (
    send_notification_event,
)
from direct_payment.notification.lib.user_inference_library import (
    get_user_from_wallet_or_payor_id,
)
from direct_payment.notification.models import (
    EventName,
    EventSourceSystem,
    UserIdType,
    UserType,
)
from storage import connection
from utils.braze import send_user_wallet_attributes
from utils.log import logger
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_benefit import ReimbursementWalletBenefit
from wallet.services.reimbusement_wallet_dashboard import (
    get_reimbursement_organization_settings,
)

LAST4 = "last4"
PAYMENT_METHOD_TYPE = "payment_method_type"
CARD_FUNDING = "card_funding"

log = logger(__name__)


def process_payment_gateway_message(message_dict: dict) -> bool:
    """
    This function will handle the messages sent from the payment gateway to the notification service. Will be exposed
    via REST or used by the subscription client
    Unknown message types Errors will be logged for external handling and thrown.
    :param message_dict: Dictionary
    :type Dict that can be converted into a PaymentGatewayEventMessage object
    :return: True if successgully submitted to the notification job, false otherwise.
    """
    try:
        message = PaymentGatewayEventMessage.create_from_dict(message_dict)
        event_type = message.event_type
        log.info(
            "Processing payment gateway event for notifications.", event_type=event_type
        )
        if event_type == "payment_method_attach_event":
            return _process_payment_method_attach_event(message)
        elif event_type == "payment_method_detach_event":
            return _process_payment_method_detach_event(message)
        else:
            raise PaymentGatewayMessageProcessingError(
                [f"{event_type} is not a supported event type."]
            )
    except (
        PaymentGatewayMessageProcessingError,
        BillingServicePGMessageProcessingError,
    ) as ex:
        log.error(
            "Unable to process payment gateway event message.", reasons=ex.message
        )
        raise PaymentGatewayMessageProcessingError([ex.message])


def _process_payment_method_attach_event(message: PaymentGatewayEventMessage) -> bool:
    info = _get_base_info_for_notification(message)
    if info:
        wallet_id = info["wallet_id"]
        program_overview_link = _get_program_overview_link(wallet_id)

        send_notification_event(
            user_id=str(wallet_id),
            user_id_type=UserIdType.PAYOR_ID.value,
            user_type=UserType.MEMBER.value,
            event_source_system=EventSourceSystem.PAYMENTS_GATEWAY.value,
            event_name=EventName.MMB_PAYMENT_METHOD_ADDED.value,
            event_properties={
                "program_overview_link": program_overview_link,
                "payment_method_last4": info[LAST4],
                "payment_method_type": info[PAYMENT_METHOD_TYPE],
                "card_funding": info.get(CARD_FUNDING, ""),
            },
        )

        _inject_user_added_payment_method_attribute(wallet_id)

        return True
    return False


def _process_payment_method_detach_event(message: PaymentGatewayEventMessage) -> bool:
    info = _get_base_info_for_notification(message)
    if info:
        benefit_id = _get_benefit_id_from_wallet_id(info["wallet_id"])
        send_notification_event(
            user_id=str(info["wallet_id"]),
            user_id_type=UserIdType.PAYOR_ID.value,
            user_type=UserType.MEMBER.value,
            event_source_system=EventSourceSystem.PAYMENTS_GATEWAY.value,
            event_name=EventName.MMB_PAYMENT_METHOD_REMOVED.value,
            event_properties={
                "benefit_id": benefit_id,
                "payment_method_last4": info[LAST4],
                "payment_method_type": info[PAYMENT_METHOD_TYPE],
            },
        )
        return True
    return False


def _get_payments_customer_id_from_message(
    message: PaymentGatewayEventMessage,
) -> str:
    message_payload = message.message_payload
    if "customer_id" not in message_payload:
        raise PaymentGatewayMessageProcessingError(
            ["customer_id not found in message message_payload."]
        )
    customer_id = message_payload["customer_id"]
    if customer_id is None or not customer_id.strip():
        raise PaymentGatewayMessageProcessingError(
            ["customer_id is blank or missing in message_payload."]
        )
    try:
        _ = uuid.UUID(customer_id)  # to check if its a good uuid
        return customer_id
    except ValueError:
        raise PaymentGatewayMessageProcessingError(
            [f"{customer_id=} is badly formed hexadecimal UUID string."]
        )


def _get_wallet_id(
    payment_customer_id: str,
) -> int | None:
    try:
        to_return = (
            connection.db.session.query(ReimbursementWallet.id)
            .filter_by(payments_customer_id=payment_customer_id)
            .one()[0]
        )
        log.info(f"Found member wallet {to_return} linked to {payment_customer_id}.")
        return to_return
    except (NoResultFound, MultipleResultsFound):
        log.warning(f"Found no member wallet linked to {payment_customer_id}.")
        return None


def _get_payment_method_package(
    message: PaymentGatewayEventMessage,
) -> dict[str, str]:
    message_payload = message.message_payload
    if "payment_method" not in message_payload:
        raise PaymentGatewayMessageProcessingError(
            ["payment_method not found in the message_payload."]
        )
    payment_method = message_payload["payment_method"]
    if payment_method is None:
        raise PaymentGatewayMessageProcessingError(
            ["payment_method was None in the message_payload."]
        )
    if not isinstance(payment_method, Mapping):
        raise PaymentGatewayMessageProcessingError(
            ["payment_method does not implement Mapping."]
        )

    error_msgs = []
    to_return = {}
    required = [PAYMENT_METHOD_TYPE, LAST4]
    optional = [CARD_FUNDING]
    for key in required:
        if key not in payment_method:
            error_msgs.append(f"payment_method is missing key: {key}.")
        else:
            if (val := payment_method[key]) is None or not val.strip():
                error_msgs.append(
                    f"value mapped to : {key} in payment_method is blank or None."
                )
            else:
                # TODO check if last4 has to be an int (leading 0's allowed)
                if key == LAST4 and len(last_4 := val.strip()) != 4:
                    error_msgs.append(
                        f"payment_method has {last_4=} which is not exactly 4 characters long."
                    )
                else:
                    to_return[key] = val.strip()
    for key in optional:
        if key in payment_method and payment_method[key]:
            to_return[key] = payment_method[key]
    if error_msgs:
        raise PaymentGatewayMessageProcessingError(error_msgs)

    return to_return


def _get_base_info_for_notification(message) -> dict | None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    # This is a little funky; trying to log all parts of the message that are malformed.
    error_msgs = []
    wallet_id = None
    payment_method_package = None
    try:
        payments_id = _get_payments_customer_id_from_message(message)
        wallet_id = _get_wallet_id(payments_id)
    except PaymentGatewayMessageProcessingError as e:
        error_msgs.append(e.message)
    try:
        payment_method_package = _get_payment_method_package(message)
    except PaymentGatewayMessageProcessingError as e:
        error_msgs.append(e.message)
    if error_msgs:
        raise PaymentGatewayMessageProcessingError(error_msgs)
    if wallet_id:
        payment_method_type = payment_method_package[PAYMENT_METHOD_TYPE]  # type: ignore[index] # Value of type "Optional[Dict[str, str]]" is not indexable
        last4 = payment_method_package[LAST4]  # type: ignore[index] # Value of type "Optional[Dict[str, str]]" is not indexable
        to_return = {
            "wallet_id": wallet_id,
            PAYMENT_METHOD_TYPE: payment_method_type,
            LAST4: last4,
            CARD_FUNDING: payment_method_package.get(CARD_FUNDING, ""),  # type: ignore[union-attr] # Item "None" of "Optional[Dict[str, str]]" has no attribute "get"
        }
    else:
        to_return = None
    return to_return


def _get_benefit_id_from_wallet_id(wallet_id: int) -> str | None:  # type: ignore[return] # Missing return statement
    try:
        res = (
            connection.db.session.query(ReimbursementWalletBenefit.maven_benefit_id)
            .filter(ReimbursementWalletBenefit.reimbursement_wallet_id == wallet_id)
            .one()[0]
        )
        log.info("Found maven_benefit_id", wallet_id=wallet_id, maven_benefit_id=res)
        return res
    except (NoResultFound, MultipleResultsFound):
        log.warn(
            "Found no/multiple maven_benefit_id(s)",
            wallet_id=wallet_id,
        )


def _get_program_overview_link(wallet_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    users = get_user_from_wallet_or_payor_id(wallet_id)
    program_overview_link = ""
    for user in users:
        org_settings = get_reimbursement_organization_settings(user)
        # pick the first org setting
        if org_settings:
            program_overview_link = org_settings.benefit_overview_resource.custom_url
    return program_overview_link


def _inject_user_added_payment_method_attribute(wallet_id: int) -> None:
    users = get_user_from_wallet_or_payor_id(wallet_id)
    now_ = datetime.now(timezone.utc)
    for user in users:
        send_user_wallet_attributes(
            external_id=user.esp_id, wallet_added_payment_method_datetime=now_
        )
