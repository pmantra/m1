from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TypeVar


class TwilioMessageStatusException(Exception):
    pass


# see https://www.twilio.com/docs/sms/api/message-resource#message-status-values
class TwilioMessageStatusEnum(enum.Enum):
    ACCEPTED = "accepted"
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    RECEIVING = "receiving"
    RECEIVED = "received"
    DELIVERED = "delivered"
    UNDELIVERED = "undelivered"
    FAILED = "failed"
    READ = "read"
    CANCELED = "canceled"


@dataclass(frozen=True)
class TwilioStatusWebhook:
    __slots__ = (
        "AccountSid",
        "From",
        "To",
        "MessageSid",
        "MessageStatus",
        "SmsSid",
        "SmsStatus",
        "ErrorCode",
    )
    AccountSid: str
    From: str
    To: str
    MessageSid: str
    MessageStatus: str
    SmsSid: str
    SmsStatus: str
    ErrorCode: str | None

    @classmethod
    def from_request(cls: type[SelfT], request: dict) -> SelfT:
        message_status = str(request["MessageStatus"])
        if not any(message_status == enum.value for enum in TwilioMessageStatusEnum):
            raise TwilioMessageStatusException(
                f"TwilioStatusWebhook MessageStatus was not recognized: {message_status}"
            )

        return cls(
            AccountSid=str(request["AccountSid"]),
            From=str(request["From"]),
            To=str(request["To"]),
            MessageSid=str(request["MessageSid"]),
            MessageStatus=message_status,
            SmsSid=str(request["SmsSid"]),
            SmsStatus=str(request["SmsStatus"]),
            ErrorCode=request.get(str("ErrorCode"), None),
        )

    def has_error_message_status(self) -> bool:
        return self.MessageStatus in (
            TwilioMessageStatusEnum.UNDELIVERED.value,
            TwilioMessageStatusEnum.FAILED.value,
        )


SelfT = TypeVar("SelfT", bound=TwilioStatusWebhook)
