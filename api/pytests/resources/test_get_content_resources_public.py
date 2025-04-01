# there are still legacy tests in tests/test_resources.py
import dataclasses
import datetime
from typing import Dict, Optional, Union
from unittest import mock
from unittest.mock import Mock

import pytest
from babel import Locale
from dateutil import parser
from requests.exceptions import ConnectionError

import common
import views.content
from care_plans.care_plans_service import CarePlansService
from l10n.utils import request_locale_str
from learn.models import article_type, migration
from learn.models.media_type import MediaType
from learn.models.migration import ContentfulMigrationStatus
from learn.models.resource_interaction import ResourceInteraction, ResourceType
from learn.pytests import factories as learn_factories
from learn.utils import disclaimers
from models import marketing
from models.images import Image
from models.marketing import ResourceContentTypes, ResourceOnDemandClass
from pytests import factories, freezegun
from pytests.factories import MemberProfileCarePlanFactory
from storage.connection import db

__BANNER = {
    "title": "title",
    "body": "body",
    "image": "/image.png",
    "cta": {
        "text": "cta text",
        "url": "/cta",
    },
    "secondary_cta": {
        "text": "secondary cta text",
        "url": "/secondary-cta",
    },
}

__FAKE_TIMESTAMP_STR = "2023-03-14T03:14:00"
__FAKE_TIMESTAMP = parser.parse(__FAKE_TIMESTAMP_STR)


@pytest.mark.parametrize(
    "contentful_status",
    [
        migration.ContentfulMigrationStatus.NOT_STARTED,
        migration.ContentfulMigrationStatus.IN_PROGRESS,
    ],
)
@mock.patch("common.stats.increment")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_content_resources_public_not_live(
    mock_article_service, mock_stats_incr, client, api_helpers, contentful_status
):
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=contentful_status,
        webflow_url=None,
    )

    response = client.get(f"/api/v1/content/resources/public/{resource.slug}")
    data = api_helpers.load_json(response)

    assert data["title"] == resource.title
    assert data["type"] == article_type.ArticleType.HTML

    assert not mock_article_service.called
    mock_stats_incr.assert_called_with(
        views.content.metric_name,
        pod_name=common.stats.PodNames.COCOPOD,
        tags=["article_type:html", "success:true", "preview:false"],
    )


@pytest.mark.parametrize("locale", ("en-US", None))
@mock.patch("views.content.banner_service.BannerService")
@mock.patch("common.stats.increment")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_content_resources_public_live_not_logged_in_english_locale(
    mock_article_service,
    mock_stats_incr,
    mock_banner_service_constructor,
    client,
    api_helpers,
    locale: Optional[str],
):
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        webflow_url=None,
    )

    related_reads = [
        {
            "title": "📚",
            "thumbnail": {"url": "https://h.tt/p.ss", "description": None},
            "slug": "🐌",
            "type": article_type.ArticleType.RICH_TEXT,
        }
    ]
    mock_article_service.return_value.get_value.return_value = {
        "title": resource.title,
        "related_reads": related_reads,
    }
    mock_banner_service_constructor.return_value.get_value.return_value = __BANNER
    response = client.get(
        f"/api/v1/content/resources/public/{resource.slug}?locale={locale}"
        if locale
        else f"/api/v1/content/resources/public/{resource.slug}"
    )
    data = api_helpers.load_json(response)

    assert data["title"] == resource.title
    assert data["type"] == article_type.ArticleType.RICH_TEXT
    assert data["content_type"] == resource.content_type
    assert data["id"] == str(resource.id)
    assert data["disclaimer"] == disclaimers.EN_DISCLAIMER
    assert data["related_reads"] is None
    assert data["banner"] == __BANNER

    mock_article_service.assert_called_with(
        preview=False, user_facing=True, should_localize=True
    )
    mock_article_service.return_value.get_value.assert_called_once_with(
        identifier_value=resource.slug, locale=locale
    )
    mock_banner_service_constructor.return_value.get_value.assert_called_once_with(
        "banner-unlimited-virtual-care-and-more"
    )
    mock_stats_incr.assert_called_with(
        views.content.metric_name,
        pod_name=common.stats.PodNames.COCOPOD,
        tags=["article_type:rich_text", "success:true", "preview:false"],
    )


@mock.patch("views.content.banner_service.BannerService")
@mock.patch("common.stats.increment")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_content_resources_public_live_not_logged_in_non_english_locale(
    mock_article_service,
    mock_stats_incr,
    mock_banner_service_constructor,
    client,
    api_helpers,
):
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        webflow_url=None,
    )

    related_reads = [
        {
            "title": "📚",
            "thumbnail": {"url": "https://h.tt/p.ss", "description": None},
            "slug": "🐌",
            "type": article_type.ArticleType.RICH_TEXT,
        }
    ]
    mock_article_service.return_value.get_value.return_value = {
        "title": resource.title,
        "related_reads": related_reads,
    }
    mock_banner_service_constructor.return_value.get_value.return_value = __BANNER

    locale = "fr-FR"
    response = client.get(
        f"/api/v1/content/resources/public/{resource.slug}?locale={locale}"
    )
    data = api_helpers.load_json(response)

    assert data["title"] == resource.title
    assert data["type"] == article_type.ArticleType.RICH_TEXT
    assert data["content_type"] == resource.content_type
    assert data["id"] == str(resource.id)
    assert data["disclaimer"] == disclaimers.FR_DISCLAIMER
    assert data["related_reads"] is None
    assert data["banner"] is None

    mock_article_service.assert_called_with(
        preview=False, user_facing=True, should_localize=True
    )
    mock_article_service.return_value.get_value.assert_called_once_with(
        identifier_value=resource.slug, locale=locale
    )
    mock_banner_service_constructor.assert_not_called()
    mock_stats_incr.assert_called_with(
        views.content.metric_name,
        pod_name=common.stats.PodNames.COCOPOD,
        tags=["article_type:rich_text", "success:true", "preview:false"],
    )


@freezegun.freeze_time(__FAKE_TIMESTAMP_STR)
@mock.patch("views.content.banner_service.BannerService")
@mock.patch("common.stats.increment")
@mock.patch("learn.services.article_service.ArticleService")
@mock.patch.object(CarePlansService, "send_activity_occurred")
def test_get_content_resources_public_live_logged_in(
    mock_send_activity_occurred,
    mock_article_service,
    mock_stats_incr,
    mock_banner_service_constructor,
    client,
    api_helpers,
):
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        webflow_url=None,
    )
    user = factories.EnterpriseUserFactory()

    related_reads = [
        {
            "title": "📚",
            "thumbnail": {"url": "https://h.tt/p.ss", "description": None},
            "slug": "🐌",
            "type": article_type.ArticleType.RICH_TEXT,
        }
    ]
    mock_article_service.return_value.get_value.return_value = {
        "title": resource.title,
        "related_reads": related_reads,
    }

    locale = "fr-FR"
    response = client.get(
        f"/api/v1/content/resources/public/{resource.slug}?locale={locale}",
        headers=api_helpers.json_headers(user),
    )
    data = api_helpers.load_json(response)

    assert data["title"] == resource.title
    assert data["type"] == article_type.ArticleType.RICH_TEXT
    assert data["content_type"] == resource.content_type
    assert data["id"] == str(resource.id)
    assert data["disclaimer"] == disclaimers.FR_DISCLAIMER
    assert data["related_reads"] == related_reads
    assert "banner" not in data

    mock_article_service.assert_called_with(
        preview=False, user_facing=True, should_localize=True
    )
    mock_article_service.return_value.get_value.assert_called_once_with(
        identifier_value=resource.slug, locale=locale
    )
    mock_banner_service_constructor.assert_not_called()

    mock_stats_incr.assert_called()

    mock_send_activity_occurred.assert_not_called()
    __verify_article_viewed_state(user.id, resource.slug)


@freezegun.freeze_time(__FAKE_TIMESTAMP_STR)
@mock.patch("views.content.banner_service.BannerService")
@mock.patch("common.stats.increment")
@mock.patch("learn.services.article_service.ArticleService")
@mock.patch.object(CarePlansService, "send_activity_occurred")
def test_get_content_resources_public_live_logged_in_article_already_viewed(
    _,
    mock_article_service,
    __,
    ___,
    client,
    api_helpers,
):
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        webflow_url=None,
    )
    user = factories.EnterpriseUserFactory()
    db.session.add(
        ResourceInteraction(
            user_id=user.id,
            resource_type=ResourceType.ARTICLE,
            slug=resource.slug,
            resource_viewed_at=__FAKE_TIMESTAMP,
            created_at=__FAKE_TIMESTAMP,
            modified_at=__FAKE_TIMESTAMP,
        )
    )

    related_reads = [
        {
            "title": "📚",
            "thumbnail": {"url": "https://h.tt/p.ss", "description": None},
            "slug": "🐌",
            "type": article_type.ArticleType.RICH_TEXT,
        }
    ]
    mock_article_service.return_value.get_value.return_value = {
        "title": resource.title,
        "related_reads": related_reads,
    }

    new_fake_timestamp_str = "2023-03-15T03:14:00"
    new_fake_timestamp = parser.parse(new_fake_timestamp_str)

    with freezegun.freeze_time(new_fake_timestamp_str):
        client.get(
            f"/api/v1/content/resources/public/{resource.slug}",
            headers=api_helpers.json_headers(user),
        )

    resource_interaction = db.session.query(ResourceInteraction).get(
        {
            "user_id": user.id,
            "resource_type": ResourceType.ARTICLE,
            "slug": resource.slug,
        }
    )
    assert resource_interaction.user_id == user.id
    assert resource_interaction.resource_type == ResourceType.ARTICLE
    assert resource_interaction.slug == resource.slug
    assert resource_interaction.resource_viewed_at == new_fake_timestamp
    assert resource_interaction.created_at == __FAKE_TIMESTAMP
    # modified_at doesn't seem to respect `freeze_time` for some reason 🤷


@freezegun.freeze_time(__FAKE_TIMESTAMP_STR)
@mock.patch("views.content.db")
@mock.patch("views.content.banner_service.BannerService")
@mock.patch("common.stats.increment")
@mock.patch("learn.services.article_service.ArticleService")
@mock.patch.object(CarePlansService, "send_activity_occurred")
def test_get_content_resources_public_live_logged_in_error_saving_viewed_time(
    mock_send_activity_occurred,
    mock_article_service,
    mock_stats_incr,
    mock_banner_service_constructor,
    mock_db,
    client,
    api_helpers,
):
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        webflow_url=None,
    )
    user = factories.EnterpriseUserFactory()

    related_reads = [
        {
            "title": "📚",
            "thumbnail": {"url": "https://h.tt/p.ss", "description": None},
            "slug": "🐌",
            "type": article_type.ArticleType.RICH_TEXT,
        }
    ]
    mock_article_service.return_value.get_value.return_value = {
        "title": resource.title,
        "related_reads": related_reads,
    }
    mock_db.session.execute.side_effect = Exception("🫣")

    locale = "fr-FR"
    response = client.get(
        f"/api/v1/content/resources/public/{resource.slug}?locale={locale}",
        headers=api_helpers.json_headers(user),
    )
    data = api_helpers.load_json(response)

    assert data["title"] == resource.title
    assert data["type"] == article_type.ArticleType.RICH_TEXT
    assert data["content_type"] == resource.content_type
    assert data["id"] == str(resource.id)
    assert data["disclaimer"] == disclaimers.FR_DISCLAIMER
    assert data["related_reads"] == related_reads
    assert "banner" not in data

    mock_article_service.assert_called_with(
        preview=False, user_facing=True, should_localize=True
    )
    mock_article_service.return_value.get_value.assert_called_once_with(
        identifier_value=resource.slug, locale=locale
    )
    mock_banner_service_constructor.assert_not_called()
    assert (
        mock.call(
            views.content.metric_name,
            pod_name=common.stats.PodNames.COCOPOD,
            tags=["article_type:rich_text", "success:true", "preview:false"],
        )
        in mock_stats_incr.call_args_list
    )

    mock_send_activity_occurred.assert_not_called()


@freezegun.freeze_time(__FAKE_TIMESTAMP_STR)
@mock.patch("learn.services.article_service.ArticleService")
@mock.patch.object(CarePlansService, "send_activity_occurred")
def test_get_content_resources_public_live_logged_in_calls_care_plan_service(
    mock_send_activity_occurred,
    mock_article_service,
    client,
    api_helpers,
):
    read_resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        webflow_url=None,
    )

    mock_article_service.return_value.get_value.return_value = {
        "title": read_resource.title,
    }

    user = factories.DefaultUserFactory()
    MemberProfileCarePlanFactory.create(
        user_id=user.id,
    )

    response = client.get(
        f"/api/v1/content/resources/public/{read_resource.slug}",
        headers=api_helpers.json_headers(user),
    )
    data = api_helpers.load_json(response)

    mock_article_service.assert_called_with(
        preview=False, user_facing=True, should_localize=True
    )
    assert data["title"] == read_resource.title
    args = mock_send_activity_occurred.call_args.args
    assert args[0] == user.id
    args1 = dataclasses.asdict(args[1])
    assert args1["type"] == "read"
    assert args1["resource_id"] == read_resource.id

    watch_resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        content_type="on_demand_class",
        webflow_url=None,
    )

    client.get(
        f"/api/v1/content/resources/public/{watch_resource.slug}",
        headers=api_helpers.json_headers(user),
    )

    args = mock_send_activity_occurred.call_args.args
    assert args[0] == user.id
    args1 = dataclasses.asdict(args[1])
    assert args1["type"] == "watch"
    assert args1["resource_id"] == watch_resource.id

    __verify_article_viewed_state(user.id, read_resource.slug)


@mock.patch("common.stats.increment")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_content_resources_contentful_fail(
    mock_article_service, mock_stats_incr, client, api_helpers
):
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        webflow_url=None,
    )
    mock_article_service.return_value.get_value.side_effect = Exception
    response = client.get(f"/api/v1/content/resources/public/{resource.slug}")
    data = api_helpers.load_json(response)

    assert data["title"] == resource.title
    assert data["type"] == article_type.ArticleType.HTML

    mock_article_service.return_value.get_value.assert_called_once()

    mock_stats_incr.assert_has_calls(
        [
            mock.call(
                views.content.metric_name,
                pod_name=common.stats.PodNames.COCOPOD,
                tags=["article_type:rich_text", "success:false", "preview:false"],
            ),
            mock.call(
                views.content.metric_name,
                pod_name=common.stats.PodNames.COCOPOD,
                tags=["article_type:html", "success:true", "preview:false"],
            ),
        ]
    )


@mock.patch("common.stats.increment")
def test_get_content_resources_webflow_fail(mock_stats_incr, client):
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.NOT_STARTED,
        webflow_url="https://something.test",  # will never resolve
    )

    with pytest.raises(ConnectionError):
        client.get(f"/api/v1/content/resources/public/{resource.slug}")

    mock_stats_incr.assert_called_with(
        views.content.metric_name,
        pod_name=common.stats.PodNames.COCOPOD,
        tags=["article_type:html", "success:false", "preview:false"],
    )


@mock.patch("views.content.banner_service.BannerService")
@mock.patch("common.stats.increment")
@mock.patch("learn.services.article_service.ArticleService")
def test_preview_param_true(
    mock_article_service, mock_stats_incr, mock_banner_service_constructor, client
):
    # no database calls
    slug = "🐌-🐌-🐌"

    mock_article_service.return_value.get_value.return_value = {"slug": slug}
    mock_banner_service_constructor.return_value.get_value.return_value = __BANNER

    response = client.get(f"/api/v1/content/resources/public/{slug}?preview=true")
    mock_article_service.assert_called_with(
        preview=True, user_facing=True, should_localize=True
    )
    mock_stats_incr.assert_called_with(
        views.content.metric_name,
        pod_name=common.stats.PodNames.COCOPOD,
        tags=["article_type:rich_text", "success:true", "preview:true"],
    )

    assert response.status_code == 200


@freezegun.freeze_time(__FAKE_TIMESTAMP_STR)
@mock.patch("learn.services.article_service.ArticleService")
def test_preview_param_true_with_auth(mock_article_service, client, api_helpers):
    user = factories.EnterpriseUserFactory()

    # no database calls
    slug = "🐌-🐌-🐌"
    mock_article_service.return_value.get_value.return_value = {"slug": slug}
    response = client.get(
        f"/api/v1/content/resources/public/{slug}?preview=true",
        headers=api_helpers.json_headers(user),
    )
    mock_article_service.assert_called_with(
        preview=True, user_facing=True, should_localize=True
    )

    assert response.status_code == 200
    resource_interaction = db.session.query(ResourceInteraction).get(
        {"user_id": user.id, "resource_type": ResourceType.ARTICLE, "slug": slug}
    )
    assert resource_interaction is None


@mock.patch("learn.services.article_service.ArticleService")
def test_get_content_resources_lowers_slug(mock_article_service, client):
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        webflow_url=None,
    )
    mock_article_service.return_value.get_value.return_value = {"title": resource.title}

    # uppercase the slug in the URL
    client.get(f"/api/v1/content/resources/public/{resource.slug.upper()}")

    # even so it gets called with the lowered version
    mock_article_service.return_value.get_value.assert_called_once_with(
        identifier_value=resource.slug.lower(), locale=None
    )


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_content_resources_bookmark_no_auth(
    mock_article_service, mock_contentful_service, client, api_helpers
):
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        webflow_url=None,
    )

    mock_banner_entry = Mock()
    mock_asset = Mock()

    mock_asset.url.return_value = "/image.png"

    mock_article_service.return_value.get_value.return_value = {"title": resource.title}

    mock_contentful_service.return_value.get_banner_by_slug.return_value = (
        mock_banner_entry
    )
    mock_banner_entry.fields.return_value = {
        "title": "title",
        "body": "body",
        "image": mock_asset,
        "cta_text": "cta text",
        "cta_url": "/cta",
        "secondary_cta_text": "secondary cta text",
        "secondary_cta_url": "/secondary-cta",
    }
    response = client.get(f"/api/v1/content/resources/public/{resource.slug}")
    data = api_helpers.load_json(response)

    assert data["title"] == resource.title
    assert data["type"] == article_type.ArticleType.RICH_TEXT
    assert data["disclaimer"] == disclaimers.EN_DISCLAIMER
    assert data["saved"] is None


@pytest.mark.parametrize(
    "header_locale",
    [Locale("en"), Locale("en", "US"), Locale("fr"), Locale("fr", "CA")],
)
@mock.patch("l10n.utils.get_locale")
@mock.patch("learn.utils.disclaimers.get_disclaimer_by_locale")
@mock.patch("learn.services.article_service.ArticleService")
def test_disclaimer_prefers_query_string(
    mock_article_service,
    mock_get_disclaimer,
    mock_get_locale,
    header_locale,
    client,
    api_helpers,
):
    mock_get_locale.return_value = header_locale
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        webflow_url=None,
    )
    user = factories.EnterpriseUserFactory()
    mock_article_service.return_value.get_value.return_value = {
        "title": resource.title,
    }

    query_string_locale = "fr-FR"
    response = client.get(
        f"/api/v1/content/resources/public/{resource.slug}?locale={query_string_locale}",
        headers=api_helpers.json_headers(user),
    )
    data = api_helpers.load_json(response)
    mock_get_disclaimer.assert_called_with("fr-FR")
    assert data["title"] == resource.title


@pytest.mark.parametrize(
    "header_locale",
    [Locale("en"), Locale("en", "US"), Locale("fr"), Locale("fr", "CA")],
)
@mock.patch("l10n.utils.get_locale")
@mock.patch("learn.utils.disclaimers.get_disclaimer_by_locale")
@mock.patch("learn.services.article_service.ArticleService")
def test_disclaimer_uses_header_value(
    mock_article_service,
    mock_get_disclaimer,
    mock_get_locale,
    header_locale,
    client,
    api_helpers,
):
    mock_get_locale.return_value = header_locale
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        webflow_url=None,
    )
    user = factories.EnterpriseUserFactory()
    mock_article_service.return_value.get_value.return_value = {
        "title": resource.title,
    }

    response = client.get(
        f"/api/v1/content/resources/public/{resource.slug}",
        headers=api_helpers.json_headers(user),
    )
    data = api_helpers.load_json(response)
    mock_get_disclaimer.assert_called_with(request_locale_str())
    assert data["title"] == resource.title

    mock_article_service.assert_called_with(
        preview=False, user_facing=True, should_localize=True
    )
    mock_article_service.return_value.get_value.assert_called_once_with(
        identifier_value=resource.slug, locale=None
    )


@freezegun.freeze_time(__FAKE_TIMESTAMP_STR)
@mock.patch("learn.services.article_service.ArticleService")
def test_get_content_resources_bookmark_not_saved(
    mock_article_service, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        webflow_url=None,
    )
    mock_article_service.return_value.get_value.return_value = {"title": resource.title}
    response = client.get(
        f"/api/v1/content/resources/public/{resource.slug}",
        headers=api_helpers.json_headers(user),
    )
    data = api_helpers.load_json(response)

    assert data["title"] == resource.title
    assert data["type"] == article_type.ArticleType.RICH_TEXT
    assert data["disclaimer"] == disclaimers.EN_DISCLAIMER
    assert data["saved"] is False
    __verify_article_viewed_state(user.id, resource.slug)


@freezegun.freeze_time(__FAKE_TIMESTAMP_STR)
@mock.patch("learn.services.article_service.ArticleService")
def test_get_content_resources_bookmark_saved(
    mock_article_service, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        webflow_url=None,
    )
    learn_factories.MemberSavedResourceFactory(
        member_id=user.id, resource_id=resource.id
    )
    mock_article_service.return_value.get_value.return_value = {"title": resource.title}
    response = client.get(
        f"/api/v1/content/resources/public/{resource.slug}",
        headers=api_helpers.json_headers(user),
    )
    data = api_helpers.load_json(response)

    assert data["title"] == resource.title
    assert data["type"] == article_type.ArticleType.RICH_TEXT
    assert data["disclaimer"] == disclaimers.EN_DISCLAIMER
    assert data["saved"] is True
    __verify_article_viewed_state(user.id, resource.slug)


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_on_demand_class(
    mock_read_time_service_constructor, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    resource = __create_on_demand_class_resource()

    mock_read_time_service_constructor.return_value.get_values.return_value = {}

    response = client.get(
        f"/api/v1/content/resources/metadata/{resource.id}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == __on_demand_class_resource_to_metadata(resource)


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_no_class_specific_output(
    mock_read_time_service_constructor, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    resource = factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        webflow_url=None,
    )

    mock_read_time_service_constructor.return_value.get_values.return_value = {}

    response = client.get(
        f"/api/v1/content/resources/metadata/{resource.id}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {
        "id": resource.id,
        "slug": resource.slug,
        "thumbnail": {"url": ""},
        "media_type": None,
    }


@pytest.mark.parametrize(
    argnames="content_type",
    argvalues=(
        ResourceContentTypes.article,
        ResourceContentTypes.real_talk,
        ResourceContentTypes.ask_a_practitioner,
        ResourceContentTypes.curriculum_step,
    ),
)
@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_estimated_read_time_minutes(
    mock_read_time_service_constructor,
    client,
    api_helpers,
    content_type: ResourceContentTypes,
):
    user = factories.EnterpriseUserFactory()
    resource = factories.ResourceFactory.create(
        content_type=content_type.name,
        slug="𓆑",
        contentful_status=ContentfulMigrationStatus.LIVE,
        image=Image(filetype="jpg", storage_key="key"),
    )
    mock_read_time_service_constructor.return_value.get_values_without_filtering.return_value = {
        resource.slug: 420
    }

    response = client.get(
        f"/api/v1/content/resources/metadata/{resource.id}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {
        "id": resource.id,
        "slug": resource.slug,
        "thumbnail": {"url": resource.image.asset_url()},
        "article": {
            "estimated_read_time_minutes": 420,
        },
        "media_type": MediaType.ARTICLE,
    }

    mock_read_time_service_constructor.assert_called_once_with()
    mock_read_time_service_constructor.return_value.get_values_without_filtering.assert_called_once_with(
        [resource.slug]
    )


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_no_estimated_read_time(
    mock_read_time_service_constructor, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    resource = __create_article_resource()
    mock_read_time_service_constructor.return_value.get_values_without_filtering.return_value = (
        {}
    )

    response = client.get(
        f"/api/v1/content/resources/metadata/{resource.id}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {
        "id": resource.id,
        "slug": resource.slug,
        "thumbnail": {"url": resource.image.asset_url()},
        "media_type": None,
    }

    mock_read_time_service_constructor.assert_called_once_with()
    mock_read_time_service_constructor.return_value.get_values_without_filtering.assert_called_once_with(
        [resource.slug]
    )


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_video_article(
    mock_read_time_service_constructor, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    resource = __create_article_resource()
    mock_read_time_service_constructor.return_value.get_values_without_filtering.return_value = {
        resource.slug: -1
    }

    response = client.get(
        f"/api/v1/content/resources/metadata/{resource.id}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {
        "id": resource.id,
        "slug": resource.slug,
        "thumbnail": {"url": resource.image.asset_url()},
        "media_type": MediaType.VIDEO,
    }

    mock_read_time_service_constructor.assert_called_once_with()
    mock_read_time_service_constructor.return_value.get_values_without_filtering.assert_called_once_with(
        [resource.slug]
    )


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_resource_not_found(_, client, api_helpers):
    user = factories.EnterpriseUserFactory()

    response = client.get(
        "/api/v1/content/resources/metadata/420",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 404
    data = api_helpers.load_json(response)
    assert data == {
        "errors": [{"status": 404, "title": "Specified Resource Not Found"}]
    }


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_not_logged_in(_, client, api_helpers):
    response = client.get(
        "/api/v1/content/resources/metadata/420",
    )

    assert response.status_code == 401
    data = api_helpers.load_json(response)
    assert data == {
        "errors": [
            {
                "status": 401,
                "detail": "Unauthorized",
                "title": "Unauthorized",
            }
        ],
        "message": "Unauthorized",
    }


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_marketplace_member(_, client, api_helpers):
    user = factories.DefaultUserFactory.create()

    response = client.get(
        "/api/v1/content/resources/metadata/420",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 403
    data = api_helpers.load_json(response)
    assert data == {
        "errors": [
            {
                "status": 403,
                "title": "Forbidden",
                "detail": "You do not have access to this resource",
            }
        ]
    }


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_batch_not_logged_in(_, client, api_helpers):
    response = client.get(
        "/api/v1/content/resources/metadata",
    )

    assert response.status_code == 401
    data = api_helpers.load_json(response)
    assert data == {
        "errors": [
            {
                "status": 401,
                "detail": "Unauthorized",
                "title": "Unauthorized",
            }
        ],
        "message": "Unauthorized",
    }


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_batch_marketplace_member(_, client, api_helpers):
    user = factories.DefaultUserFactory.create()

    response = client.get(
        "/api/v1/content/resources/metadata",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 403
    data = api_helpers.load_json(response)
    assert data == {
        "errors": [
            {
                "status": 403,
                "title": "Forbidden",
                "detail": "You do not have access to this resource",
            }
        ]
    }


@pytest.mark.parametrize(
    argnames="endpoint",
    argvalues=(
        "/api/v1/content/resources/metadata",
        f"/api/v1/content/resources/metadata?resource_ids={','.join(str(resource_id) for resource_id in range(1, 106))}",
        f"/api/v1/content/resources/metadata?resource_slugs={','.join(f'slug-{resource_id}' for resource_id in range(1, 106))}",
        f"/api/v1/content/resources/metadata?resource_ids={','.join(str(resource_id) for resource_id in range(1, 60))},resource_slugs={','.join(f'slug-{resource_id}' for resource_id in range(1, 60))}",
    ),
)
@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_batch_wrong_number_of_resources(
    _, client, api_helpers, endpoint
):
    user = factories.EnterpriseUserFactory()

    response = client.get(
        endpoint,
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 400
    data = api_helpers.load_json(response)
    assert data == {
        "errors": [
            {
                "status": 400,
                "title": "Bad Request",
                "detail": "Total number of resources must be between 1 and 104, inclusive.",
            }
        ]
    }


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_batch_by_resource_id(
    mock_read_time_service_constructor, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    resource_1 = __create_on_demand_class_resource(1)
    resource_2 = __create_on_demand_class_resource(2)

    mock_read_time_service_constructor.return_value.get_values.return_value = {}

    response = client.get(
        f"/api/v1/content/resources/metadata?resource_ids={resource_1.id},{resource_2.id}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {
        "resources": [
            __on_demand_class_resource_to_metadata(resource_1),
            __on_demand_class_resource_to_metadata(resource_2),
        ]
    }


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_batch_by_resource_slug(
    mock_read_time_service_constructor, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    resource_1 = __create_on_demand_class_resource(1)
    resource_2 = __create_on_demand_class_resource(2)

    mock_read_time_service_constructor.return_value.get_values.return_value = {}

    response = client.get(
        f"/api/v1/content/resources/metadata?resource_slugs={resource_1.slug},{resource_2.slug}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {
        "resources": [
            __on_demand_class_resource_to_metadata(resource_1),
            __on_demand_class_resource_to_metadata(resource_2),
        ]
    }


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_batch_by_resource_id_and_slug(
    mock_read_time_service_constructor, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    resource_1 = __create_on_demand_class_resource(1)
    resource_2 = __create_on_demand_class_resource(2)

    mock_read_time_service_constructor.return_value.get_values.return_value = {}

    response = client.get(
        f"/api/v1/content/resources/metadata?resource_ids={resource_1.id}&resource_slugs={resource_2.slug}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {
        "resources": [
            __on_demand_class_resource_to_metadata(resource_1),
            __on_demand_class_resource_to_metadata(resource_2),
        ]
    }


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_batch_duplicate_resource_id(
    mock_read_time_service_constructor, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    resource = __create_on_demand_class_resource()

    mock_read_time_service_constructor.return_value.get_values.return_value = {}

    response = client.get(
        f"/api/v1/content/resources/metadata?resource_ids={resource.id},{resource.id}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {
        "resources": [
            __on_demand_class_resource_to_metadata(resource),
        ],
    }


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_batch_articles(
    mock_read_time_service_constructor, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    resource_1 = __create_article_resource(1)
    resource_2 = __create_article_resource(2)

    mock_read_time_service_constructor.return_value.get_values_without_filtering.return_value = {
        resource_1.slug: 1,
        resource_2.slug: -1,
    }

    response = client.get(
        f"/api/v1/content/resources/metadata?resource_ids={resource_1.id},{resource_2.id}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {
        "resources": [
            {
                "id": resource_1.id,
                "slug": resource_1.slug,
                "thumbnail": {
                    "url": resource_1.image.asset_url(),
                },
                "article": {
                    "estimated_read_time_minutes": 1,
                },
                "media_type": MediaType.ARTICLE,
            },
            {
                "id": resource_2.id,
                "slug": resource_2.slug,
                "thumbnail": {"url": resource_2.image.asset_url()},
                "media_type": MediaType.VIDEO,
            },
        ]
    }
    mock_read_time_service_constructor.return_value.get_values_without_filtering.assert_called_once_with(
        [resource_1.slug, resource_2.slug]
    )


@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_resource_metadata_batch_one_resource_does_not_exist(
    mock_read_time_service_constructor, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    resource = __create_on_demand_class_resource()

    mock_read_time_service_constructor.return_value.get_values.return_value = {}

    response = client.get(
        f"/api/v1/content/resources/metadata?resource_ids={resource.id},420",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {
        "resources": [
            __on_demand_class_resource_to_metadata(resource),
        ]
    }


@pytest.mark.skip(reason="Test seems to sometimes reach out to third party in CI.")
@freezegun.freeze_time(__FAKE_TIMESTAMP_STR)
@mock.patch("views.content.banner_service.BannerService")
@mock.patch("common.stats.increment")
@mock.patch("learn.services.article_service.ArticleService")
@mock.patch.object(CarePlansService, "send_activity_occurred")
def test_save_on_demand_view_state(
    mock_send_activity_occurred,
    mock_article_service,
    mock_stats_incr,
    mock_banner_service_constructor,
    client,
    api_helpers,
):
    user = factories.EnterpriseUserFactory()
    resource = __create_on_demand_class_resource()

    client.get(
        f"/api/v1/content/resources/public/{resource.slug}",
        headers=api_helpers.json_headers(user),
    )
    __verify_article_viewed_state(user.id, resource.slug, ResourceType.ON_DEMAND_CLASS)


def __create_on_demand_class_resource(_id: int = 1):
    return factories.ResourceFactory.create(
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(weeks=1),
        resource_type=marketing.ResourceTypes.ENTERPRISE,
        content_type=ResourceContentTypes.on_demand_class.name,
        title="What are you doing in my swamp?",
        slug=f"what-are-you-doing-in-my-swamp-{_id}",
        id=_id,
        image=Image(filetype="jpg", storage_key=f"ogres-have-layers-{_id}"),
        on_demand_class_fields=ResourceOnDemandClass(
            instructor="Shrek", length=datetime.timedelta(hours=1, minutes=30)
        ),
    )


def __create_article_resource(_id: int = 1):
    return factories.ResourceFactory.create(
        id=_id,
        content_type=ResourceContentTypes.article.name,
        slug=f"𓆑-{_id}",
        contentful_status=ContentfulMigrationStatus.LIVE,
        image=Image(filetype="jpg", storage_key=f"key={_id}"),
    )


def __on_demand_class_resource_to_metadata(resource):
    return {
        "id": resource.id,
        "slug": resource.slug,
        "thumbnail": {"url": resource.image.asset_url()},
        "on_demand_class": __on_demand_class_resource_to_response_structure(resource),
        "media_type": MediaType.ON_DEMAND_CLASS.value,
    }


def __on_demand_class_resource_to_response_structure(
    resource,
) -> Dict[str, Union[str, Dict[str, str]]]:
    return {
        "title": resource.title,
        "slug": resource.slug,
        "id": str(resource.id),
        "image": {
            "original": resource.image.asset_url(None, None),
            "hero": resource.image.asset_url(428, 760, smart=False),
            "thumbnail": resource.image.asset_url(90, 120, smart=False),
        },
        "instructor": resource.on_demand_class_fields.instructor,
        "length": "01:30",
        "type": "html",
        "media_type": MediaType.ON_DEMAND_CLASS.value,
    }


def __verify_article_viewed_state(
    user_id: str, slug: str, resource_type: ResourceType = ResourceType.ARTICLE
):
    resource_interaction = db.session.query(ResourceInteraction).get(
        {"user_id": user_id, "resource_type": resource_type, "slug": slug}
    )
    assert resource_interaction.user_id == user_id
    assert resource_interaction.resource_type == resource_type
    assert resource_interaction.slug == slug
    assert resource_interaction.resource_viewed_at == __FAKE_TIMESTAMP
    assert resource_interaction.created_at == __FAKE_TIMESTAMP
    assert resource_interaction.modified_at == __FAKE_TIMESTAMP
