from typing import Dict
from unittest import mock

import pytest

from learn.resources import webhook
from learn.services import contentful

__ACTION = "delete"
__ENTITY_TYPE = contentful.EntityType.ASSET
__ENTITY_ID = "42"


@pytest.fixture
def headers() -> Dict[str, str]:
    return {
        "X-Contentful-Topic": f"{__ENTITY_TYPE.value}.{__ACTION}",
        "X-Contentful-Entity-Type": __ENTITY_TYPE.value,
        "X-Contentful-Entity-ID": __ENTITY_ID,
        "X-Contentful-Content-Type": "undefined",
    }


@mock.patch.object(
    webhook.LearnContentfulWebhook.CONTENTFUL_LEARN_WEBHOOK_SECRET, "primary", "shhh.."
)
@mock.patch("learn.resources.webhook.contentful_event_handler.ContentfulEventHandler")
def test_get_webhook_asset(
    mock_contentful_event_handler_constructor, headers, client, api_helpers
):
    headers["X-Maven-Contentful-Secret"] = "shhh.."
    response = client.get(
        "/api/v1/library/contentful/webhook",
        headers=headers,
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {"action": __ACTION, "type": __ENTITY_TYPE, "entity_id": __ENTITY_ID}
    mock_contentful_event_handler_constructor.return_value.handle_event.assert_called_once_with(
        __ACTION, __ENTITY_TYPE, "undefined", __ENTITY_ID
    )


@mock.patch.object(
    webhook.LearnContentfulWebhook.CONTENTFUL_LEARN_WEBHOOK_SECRET, "primary", "shhh.."
)
@mock.patch("learn.resources.webhook.contentful_event_handler.ContentfulEventHandler")
def test_get_webhook_entry(
    mock_contentful_event_handler_constructor, headers, client, api_helpers
):
    headers["X-Maven-Contentful-Secret"] = "shhh.."
    headers["X-Contentful-Topic"] = f"{contentful.EntityType.ENTRY.value}.{__ACTION}"
    headers[
        "X-Contentful-Content-Type"
    ] = contentful.ContentfulContentType.ARTICLE.value
    headers["X-Contentful-Entity-Type"] = contentful.EntityType.ENTRY.value
    response = client.get(
        "/api/v1/library/contentful/webhook",
        headers=headers,
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {"action": __ACTION, "type": "Entry", "entity_id": __ENTITY_ID}
    mock_contentful_event_handler_constructor.return_value.handle_event.assert_called_once_with(
        __ACTION,
        contentful.EntityType.ENTRY,
        contentful.ContentfulContentType.ARTICLE.value,
        __ENTITY_ID,
    )


@mock.patch.object(
    webhook.LearnContentfulWebhook.CONTENTFUL_LEARN_WEBHOOK_SECRET, "primary", "shhh.."
)
@mock.patch.object(
    webhook.LearnContentfulWebhook.CONTENTFUL_LEARN_WEBHOOK_SECRET,
    "secondary",
    "shhh2..",
)
@mock.patch("learn.resources.webhook.contentful_event_handler.ContentfulEventHandler")
def test_get_webhook_secondary_token(_, headers, client, api_helpers):
    headers["X-Maven-Contentful-Secret"] = "shhh2.."
    response = client.get(
        "/api/v1/library/contentful/webhook",
        headers=headers,
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {"action": __ACTION, "type": __ENTITY_TYPE, "entity_id": __ENTITY_ID}


@mock.patch.object(
    webhook.LearnContentfulWebhook.CONTENTFUL_LEARN_WEBHOOK_SECRET, "primary", "shhh.."
)
@mock.patch.object(
    webhook.LearnContentfulWebhook.CONTENTFUL_LEARN_WEBHOOK_SECRET,
    "secondary",
    "shhh2..",
)
def test_get_webhook_no_token_match(headers, client):
    headers["X-Maven-Contentful-Secret"] = "don't tell"
    response = client.get(
        "/api/v1/library/contentful/webhook",
        headers=headers,
    )

    assert response.status_code == 403


@mock.patch.object(
    webhook.LearnContentfulWebhook.CONTENTFUL_LEARN_WEBHOOK_SECRET, "primary", "shhh.."
)
@mock.patch.object(
    webhook.LearnContentfulWebhook.CONTENTFUL_LEARN_WEBHOOK_SECRET,
    "secondary",
    "shhh2..",
)
def test_get_webhook_no_secret(headers, client):
    response = client.get(
        "/api/v1/library/contentful/webhook",
        headers=headers,
    )

    assert response.status_code == 403


@mock.patch.object(
    webhook.LearnContentfulWebhook.CONTENTFUL_LEARN_WEBHOOK_SECRET, "primary", "shhh.."
)
@mock.patch("learn.resources.webhook.log")
@mock.patch("learn.resources.webhook.contentful_event_handler.ContentfulEventHandler")
def test_get_webhook_error(
    mock_contentful_event_handler_constructor, log_mock, headers, client, api_helpers
):
    headers["X-Maven-Contentful-Secret"] = "shhh.."

    error = Exception("😱")
    mock_contentful_event_handler_constructor.return_value.handle_event.side_effect = (
        error
    )

    with pytest.raises(  # noqa  B017  TODO:  `assertRaises(Exception)` and `pytest.raises(Exception)` should be considered evil. They can lead to your test passing even if the code being tested is never executed due to a typo. Assert for a more specific exception (builtin or custom), or use `assertRaisesRegex` (if using `assertRaises`), or add the `match` keyword argument (if using `pytest.raises`), or use the context manager form with a target.
        Exception
    ):
        client.get(
            "/api/v1/library/contentful/webhook",
            headers=headers,
        )

    mock_contentful_event_handler_constructor.return_value.handle_event.assert_called_once_with(
        __ACTION, __ENTITY_TYPE, "undefined", __ENTITY_ID
    )
    log_mock.error.assert_called_with(
        "Unable to handle Contentful webhook event",
        action=__ACTION,
        type=__ENTITY_TYPE,
        id=__ENTITY_ID,
        error=error,
        exc=True,
    )
