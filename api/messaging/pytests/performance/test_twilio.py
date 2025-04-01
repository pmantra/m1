from pytests.db_util import enable_db_performance_warnings


def test_twilio_sms(client, api_helpers, db, default_user):
    data = {
        "AccountSid": "twilio_account_sid",
        "From": "7737737373",
        "MessageSid": "1234567890",
        "MessageStatus": "accepted",
        "SmsSid": "SMS_SID",
        "SmsStatus": "SMS_STATUS",
        "Body": "body",
    }
    expected_response_code = 200

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=4,
    ):
        res = client.post(
            "/api/v1/vendor/twilio/sms",
            data=data,
        )
        assert res.status_code == expected_response_code
