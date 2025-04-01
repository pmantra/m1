from authn.domain.service.mfa import MFAEnforcementReason


def test_get_mfa_enforcement_info_when_not_required(
    client, api_helpers, default_user, mock_mfa_service
):
    mock_mfa_service.get_user_mfa_status.return_value = (
        False,
        MFAEnforcementReason.NOT_REQUIRED,
    )

    res = client.get(
        "/api/v1/mfa/enforcement", headers=api_helpers.standard_headers(default_user)
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json["require_mfa"] is False
    assert json["mfa_enforcement_reason"] == "NOT_REQUIRED"


def test_get_mfa_enforcement_info_when_required(
    client, api_helpers, default_user, mock_mfa_service
):
    mock_mfa_service.get_user_mfa_status.return_value = (
        True,
        MFAEnforcementReason.REQUIRED_BY_ORGANIZATION,
    )

    res = client.get(
        "/api/v1/mfa/enforcement", headers=api_helpers.standard_headers(default_user)
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json["require_mfa"] is True
    assert json["mfa_enforcement_reason"] == "REQUIRED_BY_ORGANIZATION"
