import json
from unittest.mock import MagicMock

from flask.testing import FlaskClient

from authn.models.user import User
from clinical_documentation.error import MissingQueryError
from clinical_documentation.models.translated_note import (
    MPracticeProviderAddendaAndQuestionnaire,
)
from clinical_documentation.pytests.resource import provider_addenda_test_data
from pytests.factories import PractitionerUserFactory
from utils.api_interaction_mixin import APIInteractionMixin
from utils.log import logger

log = logger(__name__)


class TestProviderAppointmentResource:
    def test_get_provider_addenda_success(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_note_service_for_provider_addenda_resource: MagicMock,
        provider_addenda_and_questionnaire: MPracticeProviderAddendaAndQuestionnaire,
    ):
        mock_note_service_for_provider_addenda_resource.get_provider_addenda_and_questionnaire.return_value = (
            provider_addenda_and_questionnaire
        )
        practitioner_user = PractitionerUserFactory.create(id=1)
        response = client.get(
            "/api/v2/clinical_documentation/provider_addenda?appointment_id=997948328&practitioner_id=1",
            headers=api_helpers.json_headers(practitioner_user),
        )

        assert response.status_code == 200
        response_json = json.loads(response.data)
        expected = provider_addenda_test_data.provider_addenda_and_questionnaire
        assert response_json == expected

    def test_get_provider_addenda_without_practitioner_id(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_note_service_for_provider_addenda_resource: MagicMock,
        provider_addenda_and_questionnaire: MPracticeProviderAddendaAndQuestionnaire,
        practitioner_user: User,
    ):
        mock_note_service_for_provider_addenda_resource.get_provider_addenda_and_questionnaire.return_value = (
            provider_addenda_and_questionnaire
        )
        response = client.get(
            "/api/v2/clinical_documentation/provider_addenda?appointment_id=100",
            headers=api_helpers.json_headers(practitioner_user),
        )
        assert response.status_code == 400
        response_json = json.loads(response.data)
        assert (
            response_json
            == provider_addenda_test_data.error_message_missing_practitioner_id
        )

    def test_get_provider_addenda_without_appointment_id(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_note_service_for_provider_addenda_resource: MagicMock,
        provider_addenda_and_questionnaire: MPracticeProviderAddendaAndQuestionnaire,
        practitioner_user: User,
    ):
        mock_note_service_for_provider_addenda_resource.get_provider_addenda_and_questionnaire.return_value = (
            provider_addenda_and_questionnaire
        )
        response = client.get(
            "/api/v2/clinical_documentation/provider_addenda?practitioner_id=1",
            headers=api_helpers.json_headers(practitioner_user),
        )
        assert response.status_code == 400
        response_json = json.loads(response.data)
        assert (
            response_json
            == provider_addenda_test_data.error_message_missing_appointment_id
        )

    def test_get_provider_addenda_without_appointment_id_and_practitioner_id(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_note_service_for_provider_addenda_resource: MagicMock,
        provider_addenda_and_questionnaire: MPracticeProviderAddendaAndQuestionnaire,
        practitioner_user: User,
    ):
        mock_note_service_for_provider_addenda_resource.get_provider_addenda_and_questionnaire.return_value = (
            provider_addenda_and_questionnaire
        )
        response = client.get(
            "/api/v2/clinical_documentation/provider_addenda",
            headers=api_helpers.json_headers(practitioner_user),
        )
        assert response.status_code == 400
        response_json = json.loads(response.data)
        assert (
            response_json
            == provider_addenda_test_data.error_message_missing_appointment_id_and_practitioner_id
        )

    def test_get_provider_addenda_404(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_note_service_for_provider_addenda_resource: MagicMock,
        provider_addenda_and_questionnaire: MPracticeProviderAddendaAndQuestionnaire,
        practitioner_user: User,
    ):
        mock_note_service_for_provider_addenda_resource.get_provider_addenda_and_questionnaire.return_value = (
            provider_addenda_and_questionnaire
        )
        response = client.get(
            "/api/v2/clinical_documentation/provider_addendas",
            headers=api_helpers.json_headers(practitioner_user),
        )
        assert response.status_code == 404

    def test_get_provider_addenda_500(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_note_service_for_provider_addenda_resource: MagicMock,
        provider_addenda_and_questionnaire: MPracticeProviderAddendaAndQuestionnaire,
        practitioner_user: User,
    ):
        mock_note_service_for_provider_addenda_resource.get_provider_addenda_and_questionnaire.side_effect = (
            MissingQueryError()
        )
        response = client.get(
            "/api/v2/clinical_documentation/provider_addenda?appointment_id=100&practitioner_id=1",
            headers=api_helpers.json_headers(practitioner_user),
        )
        assert response.status_code == 500
