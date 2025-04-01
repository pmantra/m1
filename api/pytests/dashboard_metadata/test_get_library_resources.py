from unittest import mock

from learn.models import migration
from views import dashboard_metadata


@mock.patch("views.dashboard_metadata.locate_maven_library")
def test_get_library_resources_images(locate_library_mock, factories):
    user = factories.EnterpriseUserFactory()
    image_mock = mock.Mock()
    url = "i.mg/img.img"
    image_mock.asset_url.return_value = url

    resource_mock = mock.Mock(subhead=None, image=image_mock)
    locate_library_mock.return_value = [resource_mock]

    result = dashboard_metadata.get_library_resources(
        user, "pregnancy", "week-5", user.organization
    )

    assert result.maven[0].icon == url


@mock.patch("views.dashboard_metadata.article_thumbnail_service")
def test_locate_maven_library(cache_mock, factories):
    resource = factories.ResourceFactory(
        phases=[("pregnancy", "week-5")],
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
    )
    thumb_service_mock = mock.Mock()
    cache_mock.ArticleThumbnailService.return_value = thumb_service_mock

    dashboard_metadata.locate_maven_library(track_name="pregnancy", phase_name="week-5")

    thumb_service_mock.get_thumbnails_for_resources.assert_called_with([resource])
