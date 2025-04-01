import json
from unittest.mock import MagicMock

from flask.testing import FlaskClient

from authn.models.user import User
from mpractice.error import MissingMemberError
from mpractice.models.translated_appointment import TranslatedProviderAppointment
from mpractice.pytests.resource import provider_appointment_test_data
from pytests.factories import PractitionerUserFactory
from utils.api_interaction_mixin import APIInteractionMixin
from utils.log import logger

log = logger(__name__)


class TestProviderAppointmentResource:
    def test_get_appointment_by_id_success(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_provider_appointment_service_for_appointment_resource: MagicMock,
        translated_provider_appointment_100: TranslatedProviderAppointment,
    ):
        mock_provider_appointment_service_for_appointment_resource.get_provider_appointment_by_id.return_value = (
            translated_provider_appointment_100
        )
        practitioner_user = PractitionerUserFactory.create(
            id=translated_provider_appointment_100.product.practitioner.id
        )
        response = client.get(
            "/api/v1/mpractice/appointment/100",
            headers=api_helpers.json_headers(practitioner_user),
        )

        assert response.status_code == 200
        response_json = json.loads(response.data)
        expected = provider_appointment_test_data.provider_appointment
        assert response_json == expected
        mock_provider_appointment_service_for_appointment_resource.get_provider_appointment_by_id.assert_called_once_with(
            997948328, practitioner_user
        )

    def test_get_appointment_by_id_403(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_provider_appointment_service_for_appointment_resource: MagicMock,
        translated_provider_appointment_100: TranslatedProviderAppointment,
    ):
        mock_provider_appointment_service_for_appointment_resource.get_provider_appointment_by_id.return_value = (
            translated_provider_appointment_100
        )
        practitioner_user_not_in_appointment = PractitionerUserFactory.create(
            id=translated_provider_appointment_100.product.practitioner.id + 1
        )
        response = client.get(
            "/api/v1/mpractice/appointment/100",
            headers=api_helpers.json_headers(practitioner_user_not_in_appointment),
        )
        assert response.status_code == 403

    def test_get_appointment_by_id_404(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_provider_appointment_service_for_appointment_resource: MagicMock,
        translated_provider_appointment_100: TranslatedProviderAppointment,
    ):
        mock_provider_appointment_service_for_appointment_resource.get_provider_appointment_by_id.return_value = (
            None
        )
        practitioner_user = PractitionerUserFactory.create(
            id=translated_provider_appointment_100.product.practitioner.id
        )
        response = client.get(
            "/api/v1/mpractice/appointment/100",
            headers=api_helpers.json_headers(practitioner_user),
        )
        assert response.status_code == 404

    def test_get_appointment_by_id_500(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_provider_appointment_service_for_appointment_resource: MagicMock,
        practitioner_user: User,
    ):
        mock_provider_appointment_service_for_appointment_resource.get_provider_appointment_by_id.side_effect = (
            MissingMemberError()
        )
        response = client.get(
            "/api/v1/mpractice/appointment/100",
            headers=api_helpers.json_headers(practitioner_user),
        )
        assert response.status_code == 500
