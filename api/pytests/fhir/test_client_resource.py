from unittest.mock import patch

import pytest

from utils.fhir_requests import FHIRClient


@patch("utils.fhir_requests.FHIRResource")
def test_resource_getter_avoids_lowercase_names(mock_resource_class):
    client = FHIRClient()

    with pytest.raises(AttributeError):
        client.condition

    mock_resource_class.assert_not_called()


@patch("utils.fhir_requests.FHIRResource")
def test_resource_getter_generation_for_capitalized_names(mock_resource_class):
    client = FHIRClient()
    client.Condition
    mock_resource_class.assert_called_with(client, "Condition")


def test_resource_read_calls_get():
    client = FHIRClient()
    with patch.object(client, "get") as mock_get:
        client.Condition.read("foo-bar-baz")
        mock_get.assert_called_with("Condition/foo-bar-baz")


def test_resource_create_calls_post():
    client = FHIRClient()
    with patch.object(client, "post") as mock_post:
        client.Condition.create({"foo": "bar"})
        mock_post.assert_called_with("Condition", data={"foo": "bar"})


def test_resource_update_calls_put():
    client = FHIRClient()
    with patch.object(client, "put") as mock_put:
        client.Condition.update("foo-bar-baz", {"foo": "bar"})
        mock_put.assert_called_with("Condition/foo-bar-baz", data={"foo": "bar"})


def test_resource_update_partial_calls_patch():
    client = FHIRClient()
    with patch.object(client, "patch") as mock_patch:
        client.Condition.update_partial("foo-bar-baz", {"foo": "bar"})
        mock_patch.assert_called_with("Condition/foo-bar-baz", data={"foo": "bar"})


def test_resource_destroy_calls_delete():
    client = FHIRClient()
    with patch.object(client, "delete") as mock_delete:
        client.Condition.destroy("foo-bar-baz")
        mock_delete.assert_called_with("Condition/foo-bar-baz")


def test_resource_search_calls_resource_post_search():
    client = FHIRClient()
    with patch.object(client, "post") as mock_post:
        client.Condition.search(a=1, b=2)
        mock_post.assert_called_with(
            "Condition/_search", params={"a": 1, "b": 2}, force=True
        )


def test_resource_search_by_identifiers_builds_query_values():
    client = FHIRClient()
    with patch.object(client, "post") as mock_post:
        client.Condition.search_by_identifiers(a=1, b=2)
        mock_post.assert_called_with(
            "Condition/_search",
            params={
                "identifier": {
                    "1",
                    "2",
                }
            },
            force=True,
        )
