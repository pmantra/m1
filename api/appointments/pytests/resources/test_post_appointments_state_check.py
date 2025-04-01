import json
from unittest.mock import patch

import pytest


@pytest.mark.parametrize("bool_variation", [True, False])
@patch("services.common.feature_flags.bool_variation")
def test_create_appointment_no_state(
    mock_bool_variation,
    client,
    api_helpers,
    setup_post_appointment_state_check,
    patch_authorize_payment,
    bool_variation,
):
    mock_bool_variation.return_value = bool_variation
    """Tests that member is able to create appointment when member's profile state does not exist and practitioner has certified state"""
    setup_values = setup_post_appointment_state_check()
    member = setup_values.member
    data = setup_values.data

    member.member_profile.state = None

    res = client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)

    assert res.status_code == 201
    if bool_variation:
        assert res_data["appointment_type"] == "education_only"
        assert res_data["privilege_type"] == "education_only"
        assert res_data["privacy"] == "basic"
    else:
        assert res_data["appointment_type"] == "anonymous"


@pytest.mark.parametrize("bool_variation", [True, False])
@patch("services.common.feature_flags.bool_variation")
def test_create_appointment_wrong_state_anon(
    mock_bool_variation,
    client,
    api_helpers,
    setup_post_appointment_state_check,
    create_state,
    patch_authorize_payment,
    bool_variation,
):
    mock_bool_variation.return_value = bool_variation

    """Tests that member is able to create appointment when member's profile state does not match practitioner's state but privacy is anonymous"""
    setup_values = setup_post_appointment_state_check()
    member = setup_values.member
    data = setup_values.data

    # set member state to be a state that is not in the list of practitioner's certified states
    member_state = create_state(name="New York", abbreviation="NY")
    member.member_profile.state = member_state

    res = client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 201
    res_data = json.loads(res.data)
    if bool_variation:
        assert res_data["appointment_type"] == "education_only"
        assert res_data["privilege_type"] == "education_only"
        assert res_data["privacy"] == "basic"
    else:
        assert res_data["appointment_type"] == "anonymous"


@pytest.mark.parametrize("bool_variation", [True, False])
@patch("services.common.feature_flags.bool_variation")
def test_create_appointment_right_state(
    mock_bool_variation,
    client,
    api_helpers,
    setup_post_appointment_state_check,
    create_state,
    patch_authorize_payment,
    bool_variation,
):
    mock_bool_variation.return_value = bool_variation

    """Tests that member is able to create appointment when member's profile state matches the practitioner's state"""
    setup_values = setup_post_appointment_state_check()
    member = setup_values.member
    data = setup_values.data

    # set member state to be a state that matches one of the practitioner's certified states
    member_state = create_state(name="New Jersey", abbreviation="NJ")
    member.member_profile.state = member_state

    res = client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 201
    res_data = json.loads(res.data)
    assert res_data["appointment_type"] == "standard"
    assert res_data["privilege_type"] == "standard"
    assert res_data["privacy"] == "basic"
