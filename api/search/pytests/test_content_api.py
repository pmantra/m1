from unittest import mock

import pytest


@pytest.fixture
def mock_contentful_builder():
    with mock.patch(
        "search.resources.content.build_article_record_from_contentful_resource_slugs"
    ) as m:
        yield m


@pytest.fixture
def mock_not_contentful_builder():
    with mock.patch(
        "search.resources.content.build_article_record_from_not_contentful_resource_slugs"
    ) as m:
        yield m


@pytest.fixture
def mock_course_builder():
    with mock.patch(
        "search.resources.content.build_course_record_from_course_slugs"
    ) as m:
        yield m


@pytest.fixture
def mock_event_builder():
    with mock.patch(
        "search.resources.content.build_virtual_event_record_from_event_ids"
    ) as m:
        yield m


class TestContentSingleResource:
    def test_get_with_contentful_source(self, client, mock_contentful_builder):
        resource_slug = "test-article"
        expected_response = {"title": "Test Article", "content": "Test content"}
        mock_contentful_builder.return_value = {resource_slug: expected_response}

        response = client.get(f"/api/v1/-/search/content/{resource_slug}")

        assert response.json == expected_response
        mock_contentful_builder.assert_called_once_with([resource_slug])

    def test_get_with_not_contentful_source(self, client, mock_not_contentful_builder):
        resource_slug = "test-article"
        expected_response = {"title": "Test Article", "content": "Test content"}
        mock_not_contentful_builder.return_value = {resource_slug: expected_response}

        request_data = {"content_source": "NOT_CONTENTFUL"}

        response = client.get(
            f"/api/v1/-/search/content/{resource_slug}", query_string=request_data
        )

        assert response.status_code == 200
        assert response.json == expected_response
        mock_not_contentful_builder.assert_called_once_with([resource_slug])

    def test_get_returns_none_when_article_not_found(
        self, client, mock_contentful_builder
    ):
        resource_slug = "non-existent-article"
        mock_contentful_builder.return_value = {}

        response = client.get(f"/api/v1/-/search/content/{resource_slug}")

        assert response.status_code == 200
        assert response.json is None
        mock_contentful_builder.assert_called_once_with([resource_slug])

    def test_get_course(self, client, mock_course_builder):
        course_slug = "test-course"
        expected_response = {"title": "Test Course", "description": "Test description"}
        mock_course_builder.return_value = {course_slug: expected_response}

        request_data = {"learning_type": "COURSE"}

        response = client.get(
            f"/api/v1/-/search/content/{course_slug}", query_string=request_data
        )

        assert response.json == expected_response
        mock_course_builder.assert_called_once_with([course_slug])

    def test_get_event(self, client, mock_event_builder):
        event_id = 1
        expected_response = {"title": "Test event", "description": "Test description"}
        mock_event_builder.return_value = {event_id: expected_response}

        request_data = {"learning_type": "EVENT"}

        response = client.get(
            f"/api/v1/-/search/content/{event_id}", query_string=request_data
        )

        assert response.json == expected_response
        mock_event_builder.assert_called_once_with([event_id])
