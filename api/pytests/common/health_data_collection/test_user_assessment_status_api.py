import datetime
from unittest.mock import patch

import requests

from common.health_data_collection.models import AssessmentMetadata
from common.health_data_collection.user_assessment_status_api import (
    get_user_assessment_by_user_id_and_slug,
    get_user_assessments_by_user_id,
)


def test_get_user_assessments_by_user_id__200():
    response_body = [
        {
            "assessment_id": "1",
            "user_id": "1",
            "num_assessment_taken": 2,
            "assessment_slug": "pregnancy",
            "completed_assessment": True,
            "date_completed": datetime.datetime.utcnow(),
        }
    ]

    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: response_body

    with patch(
        "common.health_data_collection.user_assessment_status_api.make_hdc_request"
    ) as mock_request:
        mock_request.return_value = mock_response

        user_assessments = get_user_assessments_by_user_id(user_id=1)

        assert len(user_assessments) == 1


def test_get_user_assessments_by_user_id__empty_response_200():
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: []

    with patch(
        "common.health_data_collection.user_assessment_status_api.make_hdc_request"
    ) as mock_request:
        mock_request.return_value = mock_response

        user_assessments = get_user_assessments_by_user_id(user_id=1)

        assert user_assessments == []


def test_get_user_assessments_by_user_id__400():
    mock_response = requests.Response()
    mock_response.status_code = 400
    mock_response.json = lambda: {}

    with patch(
        "common.health_data_collection.user_assessment_status_api.make_hdc_request"
    ) as mock_request:
        mock_request.return_value = mock_response

        user_assessments = get_user_assessments_by_user_id(user_id=1)

        assert user_assessments == []


def test_get_user_assessment_by_id_and_slug_completed(
    user_assessment_by_slug_populated_user_assessment,
):
    response = requests.Response()
    response.status_code = 200

    response.json = lambda: user_assessment_by_slug_populated_user_assessment

    with patch(
        "common.health_data_collection.user_assessment_status_api.make_hdc_request",
        return_value=response,
    ):
        user_assessment = get_user_assessment_by_user_id_and_slug(
            user_id=1, assessment_slug="pregnancy_welcome"
        )

        assert isinstance(user_assessment, AssessmentMetadata)
        assert user_assessment.completed is True


def test_get_user_assessment_by_id_and_slug_null_assessment(
    user_assessment_by_slug_null_user_assessment,
):
    response = requests.Response()
    response.status_code = 200

    response.json = lambda: user_assessment_by_slug_null_user_assessment

    with patch(
        "common.health_data_collection.user_assessment_status_api.make_hdc_request",
        return_value=response,
    ):
        user_assessment = get_user_assessment_by_user_id_and_slug(
            user_id=1, assessment_slug="pregnancy_welcome"
        )

        assert isinstance(user_assessment, AssessmentMetadata)
        assert user_assessment.completed is False


def test_get_user_assessment_by_id_and_slug_400():
    response = requests.Response()
    response.json = lambda: {}
    response.status_code = 400

    with patch(
        "common.health_data_collection.question_api.make_hdc_request",
        return_value=response,
    ):
        user_assessment = get_user_assessment_by_user_id_and_slug(
            user_id=1, assessment_slug="pregnancy_welcome"
        )

        assert user_assessment is None
