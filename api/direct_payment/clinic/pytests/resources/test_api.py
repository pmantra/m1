from unittest import mock

from authn.models.user import User


def test_get_fertility_clinic(api_helpers, client, active_fc_user, fertility_clinic):
    """
    Test returning fertility clinic
    """
    with mock.patch("common.services.api._get_user") as mock_get_user:
        given_user = User(id=active_fc_user.user_id, active=True)
        mock_get_user.return_value = given_user
        # Act
        res = client.get(
            f"/api/v1/direct_payment/clinic/fertility_clinics/{fertility_clinic.id}",
            headers=api_helpers.standard_headers(given_user),
        )
    data = api_helpers.load_json(res)

    # Assert
    assert res.status_code == 200
    assert data["name"] == fertility_clinic.name


def test_not_found_fertility_clinic_response(
    api_helpers, client, active_fc_user, fertility_clinic
):
    """
    Test returning 404 when no matching fertility clinic is found
    """
    with mock.patch("common.services.api._get_user") as mock_get_user:
        given_user = User(id=active_fc_user.user_id, active=True)
        mock_get_user.return_value = given_user
        # Act
        res = client.get(
            f"/api/v1/direct_payment/clinic/fertility_clinics/{fertility_clinic.id+100}",
            headers=api_helpers.standard_headers(given_user),
        )
    data = api_helpers.load_json(res)

    # Assert
    assert res.status_code == 404
    assert data["message"] == "Matching fertility clinic not found"


def test_get_fertility_clinic_no_fc_user(
    api_helpers, client, active_fc_user, fertility_clinic
):
    """
    Test returning 401 when no user is found
    """
    with mock.patch("common.services.api._get_user") as mock_get_user:
        given_user = User(id=active_fc_user.user_id, active=True)
        mock_get_user.return_value = None
        # Act
        res = client.get(
            f"/api/v1/direct_payment/clinic/fertility_clinics/{fertility_clinic.id}",
            headers=api_helpers.standard_headers(given_user),
        )

    # Assert
    assert res.status_code == 401


def test_put_fertility_clinic(api_helpers, client, active_fc_user, fertility_clinic):
    """
    Test updating the payments_recipient_id for a fertility clinic
    """
    # Arrange
    request_data = {"payments_recipient_id": "456"}

    with mock.patch("common.services.api._get_user") as mock_get_user:
        given_user = User(id=active_fc_user.user_id, active=True)
        mock_get_user.return_value = given_user
        # Act
        res = client.put(
            f"/api/v1/direct_payment/clinic/fertility_clinics/{fertility_clinic.id}",
            headers=api_helpers.standard_headers(given_user),
            json=request_data,
        )
    data = api_helpers.load_json(res)

    # Assert
    assert res.status_code == 200
    assert data["payments_recipient_id"] == fertility_clinic.payments_recipient_id


@mock.patch("direct_payment.clinic.repository.clinic.FertilityClinicRepository.put")
def test_put_errors_without_payments_recipient_id(
    mock_repository_put, api_helpers, client, active_fc_user, fertility_clinic
):
    """
    Test not sending a payments_recipient_id for a fertility clinic update errors
    """
    with mock.patch("common.services.api._get_user") as mock_get_user:
        given_user = User(id=active_fc_user.user_id, active=True)
        mock_get_user.return_value = given_user
        # Act
        res = client.put(
            f"/api/v1/direct_payment/clinic/fertility_clinics/{fertility_clinic.id}",
            headers=api_helpers.json_headers(given_user),
        )

    # Assert
    assert res.status_code == 400
    assert "Bad Request" in res.get_data(as_text=True)
    assert not mock_repository_put.called


@mock.patch("direct_payment.clinic.repository.clinic.FertilityClinicRepository.put")
def test_put_errors_without_payments_recipient_id_unsupported_media_type(
    mock_repository_put, api_helpers, client, active_fc_user, fertility_clinic
):
    """
    Test not sending a payments_recipient_id for a fertility clinic update errors
    """
    with mock.patch("common.services.api._get_user") as mock_get_user:
        given_user = User(id=active_fc_user.user_id, active=True)
        mock_get_user.return_value = given_user
        # Act
        res = client.put(
            f"/api/v1/direct_payment/clinic/fertility_clinics/{fertility_clinic.id}",
            headers=api_helpers.standard_headers(given_user),
        )
    # flask version >2.1.3 behavior
    # 415 Unsupported Media Type if no request.is_json check
    # keep the existing behavior with the request.is_json check

    # Assert
    assert res.status_code == 400
    assert "Bad Request" in res.get_data(as_text=True)
    assert not mock_repository_put.called
