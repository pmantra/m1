import json
from datetime import datetime
from unittest.mock import MagicMock

from flask.testing import FlaskClient

from clinical_documentation.models.mpractice_template import (
    MPracticeTemplate,
    MPracticeTemplateLitePagination,
)
from clinical_documentation.pytests.resource import mpractice_template_test_data
from pytests.factories import PractitionerUserFactory
from utils.api_interaction_mixin import APIInteractionMixin
from utils.log import logger

log = logger(__name__)


class TestMPracticeTemplatesResource:
    def test_get_mpractice_templates_not_logged_in(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
    ):
        response = client.get(
            "/api/v1/clinical_documentation/templates",
        )

        assert response.status_code == 401

    # # todo: make resource actually rely on practitioner user
    # def test_get_mpractice_templates_unauthorized(
    #     self,
    #     client: FlaskClient,
    #     api_helpers: APIInteractionMixin,
    #     member_user,
    # ):
    #     response = client.get(
    #         "/api/v1/clinical_documentation/templates",
    #         headers=api_helpers.json_headers(member_user),
    #     )
    #
    #     assert response.status_code == 200

    def test_get_mpractice_templates_no_templates(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
    ):
        practitioner_user = PractitionerUserFactory.create(id=3)
        response = client.get(
            "/api/v1/clinical_documentation/templates",
            headers=api_helpers.json_headers(practitioner_user),
        )

        assert response.status_code == 200
        response_json = json.loads(response.data)
        # expected = [mpractice_template_test_data.template_for_user_3, mpractice_template_test_data.second_template_for_user_3]
        assert response_json == {
            "data": [],
            "pagination": {"order_direction": "asc", "total": 0},
        }

    def test_get_mpractice_templates_has_templates(
        self,
        client: FlaskClient,
        mock_mpractice_template_service_for_multiple_resource: MagicMock,
        api_helpers: APIInteractionMixin,
    ):
        practitioner_user = PractitionerUserFactory.create(id=3)

        templates = [
            MPracticeTemplate(
                id=0,
                owner_id=practitioner_user.id,
                created_at=datetime(2024, 1, 1, 0, 0, 0),
                modified_at=datetime(2024, 1, 3, 0, 0, 0),
                sort_order=0,
                is_global=False,
                title="Sample title",
                text="Sample text",
            ),
            MPracticeTemplate(
                id=1,
                owner_id=practitioner_user.id,
                created_at=datetime(2024, 1, 2, 0, 0, 0),
                modified_at=datetime(2024, 1, 2, 0, 0, 0),
                sort_order=0,
                is_global=False,
                title="Sample title 2",
                text="Sample text but with a [template_variable] in it",
            ),
        ]

        pagination = MPracticeTemplateLitePagination(order_direction="asc", total=2)

        mock_mpractice_template_service_for_multiple_resource.get_sorted_mpractice_templates.return_value = (
            templates,
            pagination,
        )

        response = client.get(
            "/api/v1/clinical_documentation/templates",
            headers=api_helpers.json_headers(practitioner_user),
        )

        assert response.status_code == 200
        response_json = json.loads(response.data)
        expected = {
            "data": [
                mpractice_template_test_data.template_for_user_3,
                mpractice_template_test_data.second_template_for_user_3,
            ],
            "pagination": {"order_direction": "asc", "total": 2},
        }
        assert response_json == expected

    def test_create_mpractice_template_not_logged_in(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
    ):
        response = client.post(
            "/api/v1/clinical_documentation/templates",
            headers=api_helpers.json_headers(None),
        )

        assert response.status_code == 401

    def test_create_mpractice_template_invalid_payload(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
    ):
        practitioner_user = PractitionerUserFactory.create(id=3)

        response = client.post(
            "/api/v1/clinical_documentation/templates",
            data=json.dumps(
                {
                    "title": "Sample title",
                    "sort_order": 0,
                    "is_global": False,
                }
            ),
            headers=api_helpers.json_headers(practitioner_user),
        )

        assert response.status_code == 400

    def test_create_mpractice_template_same_name(
        self,
        client: FlaskClient,
        created_mpractice_template,
        api_helpers: APIInteractionMixin,
    ):
        practitioner_user = PractitionerUserFactory.create(
            id=created_mpractice_template.owner_id
        )

        response = client.post(
            "/api/v1/clinical_documentation/templates",
            data=json.dumps(
                {
                    "title": created_mpractice_template.title,
                    "text": "Different text",
                    "sort_order": 0,
                    "is_global": False,
                }
            ),
            headers=api_helpers.json_headers(practitioner_user),
        )

        assert response.status_code == 409

    def test_create_mpractice_template_success(
        self,
        client: FlaskClient,
        mock_mpractice_template_service_for_multiple_resource: MagicMock,
        api_helpers: APIInteractionMixin,
    ):
        mock_mpractice_template_service_for_multiple_resource.create_mpractice_template.return_value = MPracticeTemplate(
            id=0,
            owner_id=3,
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            modified_at=datetime(2024, 1, 3, 0, 0, 0),
            sort_order=0,
            is_global=False,
            title="Sample title",
            text="Sample text",
        )

        practitioner_user = PractitionerUserFactory.create(id=3)

        response = client.post(
            "/api/v1/clinical_documentation/templates",
            data=json.dumps(
                {
                    "title": "Sample title",
                    "text": "Sample text",
                    "sort_order": 0,
                    "is_global": False,
                }
            ),
            headers=api_helpers.json_headers(practitioner_user),
        )

        assert response.status_code == 201
        assert response.json == {
            "data": mpractice_template_test_data.template_for_user_3
        }


class TestMPracticeTemplateResource:
    def test_edit_mpractice_template_not_logged_in(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
    ):
        response = client.patch(
            "/api/v1/clinical_documentation/templates/0",
            headers=api_helpers.json_headers(None),
        )

        assert response.status_code == 401

    def test_edit_mpractice_template_invalid_payload(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
    ):
        practitioner_user = PractitionerUserFactory.create(id=3)

        response = client.patch(
            "/api/v1/clinical_documentation/templates/0",
            data=json.dumps(
                {
                    "sort_order": 0,
                    "is_global": False,
                }
            ),
            headers=api_helpers.json_headers(practitioner_user),
        )

        assert response.status_code == 400

    def test_edit_mpractice_template_does_not_exist(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
    ):
        practitioner_user = PractitionerUserFactory.create(id=3)

        response = client.patch(
            "/api/v1/clinical_documentation/templates/0",
            data=json.dumps(
                {
                    "title": "New",
                }
            ),
            headers=api_helpers.json_headers(practitioner_user),
        )

        assert response.status_code == 404

    def test_edit_mpractice_template_success(
        self,
        client: FlaskClient,
        mock_mpractice_template_service_for_singleton_resource,
        api_helpers: APIInteractionMixin,
    ):
        practitioner_user = PractitionerUserFactory.create(id=3)

        mock_mpractice_template_service_for_singleton_resource.edit_mpractice_template_by_id.return_value = MPracticeTemplate(
            id=0,
            owner_id=3,
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            modified_at=datetime(2024, 1, 3, 0, 0, 0),
            sort_order=0,
            is_global=False,
            title="New title",
            text="Sample text",
        )

        response = client.patch(
            "/api/v1/clinical_documentation/templates/0",
            data=json.dumps(
                {
                    "title": "New title",
                }
            ),
            headers=api_helpers.json_headers(practitioner_user),
        )

        expected = mpractice_template_test_data.template_for_user_3
        expected["title"] = "New title"

        assert response.status_code == 200
        assert response.json == {"data": expected}

    def test_delete_mpractice_template_not_logged_in(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
    ):
        response = client.delete(
            "/api/v1/clinical_documentation/templates/0",
            headers=api_helpers.json_headers(None),
        )

        assert response.status_code == 401

    def test_delete_mpractice_template_does_not_exist(
        self,
        client: FlaskClient,
        mock_mpractice_template_service_for_singleton_resource,
        api_helpers: APIInteractionMixin,
    ):
        practitioner_user = PractitionerUserFactory.create(id=3)

        mock_mpractice_template_service_for_singleton_resource.delete_mpractice_template_by_id.return_value = (
            False
        )

        response = client.delete(
            "/api/v1/clinical_documentation/templates/0",
            headers=api_helpers.json_headers(practitioner_user),
        )

        assert response.status_code == 404

    def test_delete_mpractice_template_success(
        self,
        client: FlaskClient,
        mock_mpractice_template_service_for_singleton_resource,
        api_helpers: APIInteractionMixin,
    ):
        practitioner_user = PractitionerUserFactory.create(id=3)

        mock_mpractice_template_service_for_singleton_resource.delete_mpractice_template_by_id.return_value = (
            True
        )

        response = client.delete(
            "/api/v1/clinical_documentation/templates/0",
            headers=api_helpers.json_headers(practitioner_user),
        )

        assert response.status_code == 204
