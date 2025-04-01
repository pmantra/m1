def test_create_message_as_member(message_channel_with_credits, client, api_helpers):
    message_body = "Is this thing on? Can anybody hear me in there?"

    res = client.post(
        f"/api/v1/channel/{message_channel_with_credits.id}/messages",
        headers={
            **api_helpers.standard_headers(message_channel_with_credits.member),
            **api_helpers.json_headers(),
        },
        json={"body": message_body},
    )
    assert res.status_code == 201
    assert api_helpers.load_json(res)["body"] == message_body


def test_create_message_as_practitioner(
    message_channel_with_credits, client, api_helpers
):
    message_body = "Take two of these and call me in the morning."

    res = client.post(
        f"/api/v1/channel/{message_channel_with_credits.id}/messages",
        headers={
            **api_helpers.standard_headers(message_channel_with_credits.practitioner),
            **api_helpers.json_headers(),
        },
        json={"body": message_body},
    )
    assert res.status_code == 201
    assert api_helpers.load_json(res)["body"] == message_body
