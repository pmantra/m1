import pytest


@pytest.mark.parametrize(
    ["data", "expected_response_code"],
    [
        ({}, 202),
        ({"bad": "data"}, 202),
        (
            {
                "AccountSid": "INVALID_SID",
                "From": "1231231234",
                "To": "12345678910",
                "MessageSid": "1234567890",
                "MessageStatus": "accepted",
                "SmsSid": "SMS_SID",
                "SmsStatus": "SMS_STATUS",
            },
            202,
        ),
        (
            {
                "AccountSid": "twilio_account_sid",
                "From": "1231231234",
                "To": "12345678910",
                "MessageSid": "1234567890",
                "MessageStatus": "accepted",
                "SmsSid": "SMS_SID",
                "SmsStatus": "SMS_STATUS",
            },
            204,
        ),
        (
            {
                "AccountSid": "twilio_account_sid",
                "From": "1231231234",
                "To": "12345678910",
                "MessageSid": "1234567890",
                "MessageStatus": "failed",
                "SmsSid": "SMS_SID",
                "SmsStatus": "SMS_STATUS",
            },
            204,
        ),
    ],
)
def test_twilio_message_status_webhook(client, data, expected_response_code):

    res = client.post(
        "/api/v1/vendor/twilio/message_status",
        data=data,
    )

    assert res.status_code == expected_response_code
