import datetime
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from utils import index_resources


@patch("utils.index_resources.get_client")
@patch("utils.index_resources.log")
def test_run_filters_ineligible_resources(log_mock, get_client_mock, factories):
    tag = factories.TagFactory()
    # Eligible resource: published, has an allowed track and a tag, normal content type
    resource = factories.ResourceFactory(
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        # Otherwise this method actually tries to get content from the Faker url
        webflow_url=None,
        tracks=["pregnancy"],
        tags=[tag],
    )
    # Ineligible: not published
    factories.ResourceFactory(
        published_at=datetime.datetime.now() + datetime.timedelta(days=10),
        webflow_url=None,
        tracks=["pregnancy"],
        tags=[tag],
    )
    # Ineligible: no tracks
    factories.ResourceFactory(
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=None,
        tags=[tag],
    )
    # Ineligible: no tags
    factories.ResourceFactory(
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=None,
        tracks=["pregnancy"],
    )
    # Ineligible: incorrect content type
    factories.ResourceFactory(
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=None,
        tracks=["pregnancy"],
        tags=[tag],
        content_type="connected_content",
    )

    client_mock = MagicMock()
    get_client_mock.return_value = client_mock

    index_resources.run()

    call1 = call("Building resources index", count=1)
    call2 = call("Sending resources index to app search", count=1)
    call3 = call("Sending batch of resources", count=1)
    log_mock.debug.assert_has_calls([call1, call2, call3])

    client_mock.index_documents.assert_called_with(
        ANY,
        [
            {
                "id": f"resource:{resource.id}",
                "raw_id": resource.id,
                "content_type": resource.content_type,
                "slug": resource.slug,
                "title": resource.title,
                "body_content": resource.body,
                "image_storage_key": None,
                "tracks": ["pregnancy"],
                "article_type": "html",
            }
        ],
    )


@patch("utils.index_resources.get_client")
def test_run_indexes_on_demand_classes(get_client_mock, factories):
    # No tags, no problem
    resource = factories.ResourceFactory(
        content_type="on_demand_class",
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=None,
        tracks=["pregnancy"],
    )

    client_mock = MagicMock()
    get_client_mock.return_value = client_mock

    index_resources.run()
    client_mock.index_documents.assert_called_with(
        ANY,
        [
            {
                "id": f"resource:{resource.id}",
                "content_type": "on_demand_class",
                "raw_id": resource.id,
                "slug": resource.slug,
                "title": resource.title,
                "body_content": resource.body,
                "image_storage_key": None,
                "tracks": ["pregnancy"],
                "article_type": "html",
            }
        ],
    )


@patch("utils.index_resources.app_search_enabled")
@patch("utils.index_resources.get_client")
@patch("utils.index_resources.log")
def test_remove_from_index(log_mock, get_client_mock, search_enabled_mock, factories):
    resource = factories.ResourceFactory()

    client_mock = MagicMock()
    get_client_mock.return_value = client_mock

    search_enabled_mock.return_value = True

    index_resources.remove_from_index(resource)

    log_mock.info.assert_called_with(
        "Removing resource from Elasticsearch index",
        id=resource.id,
        slug=resource.slug,
    )

    client_mock.delete_documents.assert_called_with(
        engine_name=ANY, document_ids=[f"resource:{resource.id}"]
    )


@patch("utils.index_resources.app_search_enabled")
@patch("utils.index_resources.get_client")
@patch("utils.index_resources.log")
def test_remove_from_index_error(
    log_mock, get_client_mock, search_enabled_mock, factories
):
    resource = factories.ResourceFactory()

    client_mock = MagicMock()
    error = Exception("can't")
    client_mock.delete_documents.side_effect = error
    get_client_mock.return_value = client_mock

    search_enabled_mock.return_value = True

    with pytest.raises(  # noqa  B017  TODO:  `assertRaises(Exception)` and `pytest.raises(Exception)` should be considered evil. They can lead to your test passing even if the code being tested is never executed due to a typo. Assert for a more specific exception (builtin or custom), or use `assertRaisesRegex` (if using `assertRaises`), or add the `match` keyword argument (if using `pytest.raises`), or use the context manager form with a target.
        Exception
    ):
        index_resources.remove_from_index(resource)

    log_mock.error.assert_called_with(
        "Error removing resource from Elasticsearch index",
        error=error,
        id=resource.id,
        slug=resource.slug,
    )
