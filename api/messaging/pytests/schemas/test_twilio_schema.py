import pytest

from messaging.schemas.twilio import TwilioMessageStatusEnum, TwilioStatusWebhook


@pytest.mark.parametrize(
    ["message_status", "expected"],
    [
        (TwilioMessageStatusEnum.ACCEPTED.value, False),
        (TwilioMessageStatusEnum.SCHEDULED.value, False),
        (TwilioMessageStatusEnum.QUEUED.value, False),
        (TwilioMessageStatusEnum.SENDING.value, False),
        (TwilioMessageStatusEnum.SENT.value, False),
        (TwilioMessageStatusEnum.RECEIVING.value, False),
        (TwilioMessageStatusEnum.RECEIVED.value, False),
        (TwilioMessageStatusEnum.DELIVERED.value, False),
        (TwilioMessageStatusEnum.UNDELIVERED.value, True),
        (TwilioMessageStatusEnum.FAILED.value, True),
        (TwilioMessageStatusEnum.READ.value, False),
        (TwilioMessageStatusEnum.CANCELED.value, False),
    ],
)
def test_TwilioRequest(message_status, expected):
    request_data = {
        "AccountSid": "",
        "From": "",
        "To": "",
        "MessageSid": "",
        "MessageStatus": message_status,
        "SmsSid": "",
        "SmsStatus": "",
    }
    request = TwilioStatusWebhook.from_request(request_data)
    assert expected == request.has_error_message_status()
