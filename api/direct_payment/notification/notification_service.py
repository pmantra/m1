"""
The main notification service script - containing the publicly available functions
"""
from __future__ import annotations

from traceback import format_exc
from typing import Iterable

from ddtrace import tracer

from authn.models.user import User
from direct_payment.notification.errors import (
    NotificationServiceError,
    UserInferenceError,
)
from direct_payment.notification.lib.user_inference_library import (
    get_user_from_wallet_or_payor_id,
)
from direct_payment.notification.models import (
    EventSourceSystem,
    NotificationEventPayload,
    NotificationPayload,
    NotificationStatus,
    NotificationStatusObject,
    UserIdType,
    UserType,
)
from utils.braze import send_event
from utils.log import logger

log = logger(__name__)


class NotificationService:
    """
    This class provides an interface to send notification emails.
    """

    @tracer.wrap()
    def send_notification_event(
        self,
        user_id: str,
        user_id_type: str,
        user_type: str | None,
        event_source_system: str,
        event_name: str,
        event_properties: dict,
    ) -> dict:
        """
        :param user_id: The user id as known by the calling system - used for lookup .
        :param user_id_type: The type of the user id - used for lookup
        :param user_type: The type of the user - added for future support of employers/clinics
        :param event_source_system: The system calling the service - used for logging.
        :param event_name: The event name registered in Braze.
        :param event_properties: The properties for this event
        :return: Dict of statuses for each resolved user.
        """
        try:
            payload = NotificationPayload(
                user_id=user_id,
                user_id_type=UserIdType(user_id_type),
                user_type=UserType(user_type) if user_type else None,
                event_source_system=EventSourceSystem(event_source_system),
                notification_event_payload=NotificationEventPayload.create_from_dict(
                    {"event_name": event_name, "event_properties": event_properties}
                ),
            )
        except AssertionError as ex:
            raise NotificationServiceError(ex.args)
        return self.send_notification_event_from_payload(payload)

    def send_notification_event_from_payload(
        self, payload: NotificationPayload
    ) -> dict:
        """
        :param payload: The notification payload.
        :return: Dict of statuses for each resolved user.
        """
        self._validate(payload)
        users = self._get_maven_users(payload)
        res = self._dispatch(users, payload)
        log.info(
            "Dispatched notification payload to braze",
            payload=payload,
            users=users,
            res=res,
        )
        return res

    @staticmethod
    def _validate(payload: NotificationPayload) -> None:
        msgs = []
        user_type = payload.user_type
        if user_type and user_type in [UserType.EMPLOYER, UserType.CLINIC]:
            msgs.append(
                f"Unsupported user type: {user_type}. Only member is currently supported"
            )
        if msgs:
            raise (NotificationServiceError(msgs))

    @staticmethod
    def _get_maven_users(payload: NotificationPayload) -> list[User]:
        try:
            id_type = payload.user_id_type
            # PAYOR_ID and WALLET_ID are identical - former is the term used in billing and the latter in wallet.
            # structured like this to support other ID types in future.
            if id_type not in {UserIdType.PAYOR_ID, UserIdType.WALLET_ID}:
                # should never come here
                raise UserInferenceError(
                    [f"Unsupported User id type: {id_type}. This should never happen."]
                )
            res = list(NotificationService._get_users_from_wallet_or_payor(payload))
            if not res:
                raise UserInferenceError(
                    [f"Unable to find any users for {payload.user_id}"]
                )
            return res
        except UserInferenceError as e:
            log.error("Unable to infer user", reason=e.message, payload=payload)
            raise NotificationServiceError([e.message])

    @staticmethod
    def _get_users_from_wallet_or_payor(payload) -> Iterable[User]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        inp_id = payload.user_id
        try:
            id_ = int(inp_id)
        except ValueError:
            raise UserInferenceError(f"{inp_id} is not a valid int.")
        to_return = list(get_user_from_wallet_or_payor_id(id_))
        log.info(f"Found {len(to_return)} user(s) linked to {id_}")
        return to_return

    @staticmethod
    def _dispatch(
        users: list[User], payload: NotificationPayload
    ) -> dict[str, NotificationStatusObject]:
        res = {}
        for i, user in enumerate(users):
            try:
                log.info(f"Processing user: {user.esp_id}, {i+1} of {len(users)}")
                status = send_event(
                    user=user,
                    event_name=payload.notification_event_payload.event_name.value,
                    event_data=payload.notification_event_payload.to_dict()[
                        "event_properties"
                    ],
                )
                notification_status = (
                    NotificationStatus.BRAZE_SUCCESS
                    if status["success"] == "true"
                    else NotificationStatus.BRAZE_FAILURE
                )
                res[user.esp_id] = NotificationStatusObject(
                    notification_status=notification_status,
                    braze_response=status["response"],
                    message=None,
                )
            except Exception:
                res[user.esp_id] = NotificationStatusObject(
                    notification_status=NotificationStatus.ERROR,
                    braze_response=None,
                    message=format_exc(),
                )
            if res[user.esp_id].notification_status == NotificationStatus.BRAZE_SUCCESS:
                log.info(f"Success processing: {user.esp_id}.")
            else:
                log.error(
                    f"Failure processing: {user.esp_id}.",
                    reason=res[user.esp_id].message,
                )
        return res
