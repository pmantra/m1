from pytests.factories import DefaultUserFactory


def test_wallet_historical_spend__success(
    client, api_helpers, qualified_alegeus_wallet_hra
):
    ros_id = qualified_alegeus_wallet_hra.reimbursement_organization_settings.id
    payload = {"file_id": "abc123", "reimbursement_organization_settings_id": ros_id}

    request_user = DefaultUserFactory.create()
    res = client.post(
        "/api/v1/-/wallet_historical_spend/process_file",
        headers=api_helpers.json_headers(request_user),
        data=api_helpers.json_data(payload),
    )
    assert res.status_code == 201
    content = api_helpers.load_json(res)
    assert content == "Payload received"


def test_wallet_historical_spend__bad_ros(client, api_helpers):
    payload = {"file_id": "abc123", "reimbursement_organization_settings_id": "abc123"}

    request_user = DefaultUserFactory.create()
    res = client.post(
        "/api/v1/-/wallet_historical_spend/process_file",
        headers=api_helpers.json_headers(request_user),
        data=api_helpers.json_data(payload),
    )
    assert res.status_code == 400
    content = api_helpers.load_json(res)
    assert (
        content["message"]
        == "Failed to process file. Reimbursement Organization Settings not found."
    )


def test_wallet_historical_spend__missing_body(client, api_helpers):
    payload = {"reimbursement_organization_settings_id": "abc123"}

    request_user = DefaultUserFactory.create()
    res = client.post(
        "/api/v1/-/wallet_historical_spend/process_file",
        headers=api_helpers.json_headers(request_user),
        data=api_helpers.json_data(payload),
    )
    assert res.status_code == 400
    content = api_helpers.load_json(res)
    assert content["message"] == "Failed to process file. Missing required field."
