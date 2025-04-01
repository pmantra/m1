import json
from unittest.mock import MagicMock

from flask.testing import FlaskClient

from authn.models.user import User
from clinical_documentation.error import MissingQueryError
from clinical_documentation.models.translated_note import StructuredInternalNote
from clinical_documentation.pytests.resource import structured_internal_notes_test_data
from utils.api_interaction_mixin import APIInteractionMixin

INVALID_ARGS_ERROR_MSG = "Invalid request argument to get structured internal note."


class TestStructuredInternalNotesResource:
    def test_get_structured_internal_notes_success(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_note_service_for_structured_internal_notes_resource: MagicMock,
        structured_internal_note: StructuredInternalNote,
        practitioner_user: User,
    ):
        mock_note_service_for_structured_internal_notes_resource.get_structured_internal_notes.return_value = (
            structured_internal_note
        )
        response = client.get(
            "/api/v2/clinical_documentation/structured_internal_notes?appointment_id=997948328&practitioner_id=1",
            headers=api_helpers.json_headers(practitioner_user),
        )

        assert response.status_code == 200
        response_json = json.loads(response.data)
        expected = structured_internal_notes_test_data.data
        assert response_json == expected

    def test_get_structured_internal_notes_without_practitioner_id(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_note_service_for_structured_internal_notes_resource: MagicMock,
        structured_internal_note: StructuredInternalNote,
        practitioner_user: User,
    ):

        mock_note_service_for_structured_internal_notes_resource.get_structured_internal_notes.return_value = (
            structured_internal_note
        )
        response = client.get(
            "/api/v2/clinical_documentation/structured_internal_notes?appointment_id=997948328",
            headers=api_helpers.json_headers(practitioner_user),
        )
        assert response.status_code == 400
        response_json = json.loads(response.data)
        assert response_json.get("message") == INVALID_ARGS_ERROR_MSG

    def test_get_structured_internal_notes_without_appointment_id(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_note_service_for_structured_internal_notes_resource: MagicMock,
        structured_internal_note: StructuredInternalNote,
        practitioner_user: User,
    ):
        mock_note_service_for_structured_internal_notes_resource.get_structured_internal_notes.return_value = (
            structured_internal_note
        )
        response = client.get(
            "/api/v2/clinical_documentation/structured_internal_notes?practitioner_id=997948328",
            headers=api_helpers.json_headers(practitioner_user),
        )
        assert response.status_code == 400
        response_json = json.loads(response.data)
        assert response_json.get("message") == INVALID_ARGS_ERROR_MSG

    def test_get_structured_internal_notes_without_appointment_id_and_practitioner_id(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_note_service_for_structured_internal_notes_resource: MagicMock,
        structured_internal_note: StructuredInternalNote,
        practitioner_user: User,
    ):
        mock_note_service_for_structured_internal_notes_resource.get_structured_internal_notes.return_value = (
            structured_internal_note
        )
        response = client.get(
            "/api/v2/clinical_documentation/structured_internal_notes",
            headers=api_helpers.json_headers(practitioner_user),
        )
        assert response.status_code == 400
        response_json = json.loads(response.data)
        assert response_json.get("message") == INVALID_ARGS_ERROR_MSG

    def test_get_structured_internal_notes_without_appointment_id_and_practitioner_id_404(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_note_service_for_structured_internal_notes_resource: MagicMock,
        structured_internal_note: StructuredInternalNote,
        practitioner_user: User,
    ):
        mock_note_service_for_structured_internal_notes_resource.get_structured_internal_notes.return_value = (
            structured_internal_note
        )
        response = client.get(
            "/api/v2/clinical_documentation/structured_internal_note?appointment_id=1&practitioner_id=1",
            headers=api_helpers.json_headers(practitioner_user),
        )
        assert response.status_code == 404

    def test_get_structured_internal_notes_without_appointment_id_and_practitioner_id_500(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_note_service_for_structured_internal_notes_resource: MagicMock,
        structured_internal_note: StructuredInternalNote,
        practitioner_user: User,
    ):
        mock_note_service_for_structured_internal_notes_resource.get_structured_internal_notes.side_effect = (
            MissingQueryError()
        )
        response = client.get(
            "/api/v2/clinical_documentation/structured_internal_notes?appointment_id=1&practitioner_id=1",
            headers=api_helpers.json_headers(practitioner_user),
        )
        assert response.status_code == 500
