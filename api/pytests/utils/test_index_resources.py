import datetime
from unittest import mock

import pytest

from learn.models import migration
from learn.models.course import CourseChapter
from learn.models.image import Image
from pytests.factories import (
    VirtualEventCategoryFactory,
    VirtualEventCategoryTrackFactory,
    VirtualEventFactory,
)
from utils import index_resources


@pytest.fixture
def mock_course():
    course_fields = {
        "id": 1,
        "slug": "breastfeeding-pumping-and-formula",
        "title": "Breastfeeding, pumping, and formula",
        "description": "Not sure how you’ll feed baby? Knowing your options is a great way to begin! Learn how to breast-, bottle-, or combo-feed like a pro in one course.",
        "chapters": [],
    }
    course = mock.Mock(**course_fields)
    course.image = Image(url="test_url", description="test_description")
    chapter = CourseChapter(
        slug="chapter-slug-1",
        title="Chapter title 1",
        description="chapter description 1",
        image=None,
    )
    chapter.length_in_minutes = 3
    course.chapters.append(chapter)
    return course


@mock.patch("utils.index_resources.app_search_enabled", return_value=True)
@mock.patch("utils.index_resources.log")
@mock.patch("utils.index_resources.get_client")
def test_index_contentful_article_no_resource(get_client_mock, log_mock, _):
    slug = "🐌-🐌-🐌"
    entry = mock.Mock(slug=slug)
    client_mock = mock.Mock()
    get_client_mock.return_value = client_mock

    index_resources.index_article_from_contentful_entry(entry)

    client_mock.index_documents.assert_not_called()
    log_mock.info.assert_called_with(
        "Resource not found or not eligible when attempting to add to index", slug=slug
    )


@mock.patch("utils.index_resources.app_search_enabled", return_value=True)
@mock.patch("utils.index_resources.log")
@mock.patch("utils.index_resources.get_client")
def test_index_contentful_article_not_live(get_client_mock, log_mock, _, factories):
    slug = "🐌-🐌-🐌"
    entry = mock.Mock(slug=slug)
    factories.ResourceFactory(
        slug=slug,
        tracks=["pregnancy"],
        tags=[factories.TagFactory.create()],
    )
    client_mock = mock.Mock()
    get_client_mock.return_value = client_mock

    index_resources.index_article_from_contentful_entry(entry)

    client_mock.index_documents.assert_not_called()
    log_mock.info.assert_called_with(
        "Resource not found or not eligible when attempting to add to index", slug=slug
    )


@mock.patch("utils.index_resources.app_search_enabled", return_value=True)
@mock.patch("utils.index_resources.log")
@mock.patch("utils.index_resources.get_client")
def test_index_contentful_article_not_eligible_for_search(
    get_client_mock, log_mock, _, factories
):
    slug = "🐌-🐌-🐌"
    entry = mock.Mock(slug=slug)
    factories.ResourceFactory(
        slug=slug,
        tracks=["pregnancy"],
        tags=[factories.TagFactory.create()],
        published_at=None,
    )
    client_mock = mock.Mock()
    get_client_mock.return_value = client_mock

    index_resources.index_article_from_contentful_entry(entry)

    client_mock.index_documents.assert_not_called()
    log_mock.info.assert_called_with(
        "Resource not found or not eligible when attempting to add to index", slug=slug
    )


@mock.patch("utils.index_resources.app_search_enabled", return_value=True)
@mock.patch("utils.index_resources.get_resources_engine", return_value="engine-name")
@mock.patch("requests.post")
@mock.patch("utils.index_resources.get_client")
@mock.patch("learn.utils.rich_text_utils.rich_text_to_plain_string_array")
@mock.patch("learn.models.image.Image.from_contentful_asset")
def test_index_contentful_article_eligible_for_search(
    img_mock, rich_to_plain_mock, get_client_mock, requests_mock, _, __, factories
):
    slug = "🐌-🐌-🐌"
    title = "title of the song"
    entry = mock.Mock(slug=slug, title=title)
    resource = factories.ResourceFactory(
        title="not that, something else",
        slug=slug,
        tracks=["pregnancy"],
        tags=[factories.TagFactory.create()],
        published_at=datetime.datetime.utcnow() - datetime.timedelta(days=1),
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
    )
    client_mock = mock.Mock()
    get_client_mock.return_value = client_mock

    # The rich text to plain text method doesn't have a return value, it
    # modifies an array in place, so have to mimic this with a mock side effect
    def side_effect(root_node, string_array):
        string_array += ["str1", "str2", "str3"]

    rich_to_plain_mock.side_effect = side_effect

    img_mock.return_value = mock.Mock(description="img description")
    img_mock.return_value.asset_url.return_value = "u.rl/img.img"

    with mock.patch(
        "maven.feature_flags.bool_variation",
        return_value=True,
    ):
        index_resources.index_article_from_contentful_entry(entry)

    client_mock.index_documents.assert_called_with(
        "engine-name",
        [
            {
                "id": f"resource:{resource.id}",
                "raw_id": resource.id,
                "slug": resource.slug,
                "title": title,
                "body_content": "str1 str2 str3",
                "image_url": "u.rl/img.img",
                "image_description": "img description",
                "content_type": resource.content_type,
                "tracks": ["pregnancy"],
                "article_type": "rich_text",
            }
        ],
    )
    requests_mock.assert_called_with(
        "content_event",
        headers={"Content-type": "application/json"},
        json=[
            {
                "slug": slug,
                "event_type": "UPDATE",
                "content_source": index_resources.ContentSource.CONTENTFUL,
                "learning_type": index_resources.LearningType.DEFAULT,
            }
        ],
        timeout=2,
    )


@mock.patch("utils.index_resources.log")
def test_remove_contentful_article_no_resource(log_mock):
    slug = "🐌-🐌-🐌"
    entry = mock.Mock(slug=slug)

    index_resources.remove_contentful_article_from_index(entry)

    log_mock.info.assert_called_with(
        "Resource not found or not live when attempting to remove from index", slug=slug
    )


@mock.patch("utils.index_resources.log")
def test_remove_contentful_article_resource_not_live(log_mock, factories):
    slug = "🐌-🐌-🐌"
    entry = mock.Mock(slug=slug)
    factories.ResourceFactory(slug=slug)

    index_resources.remove_contentful_article_from_index(entry)

    log_mock.info.assert_called_with(
        "Resource not found or not live when attempting to remove from index", slug=slug
    )


@mock.patch("utils.index_resources.remove_from_index")
@mock.patch("requests.post")
def test_remove_contentful_article_existing_resource(
    requests_mock, remove_mock, factories
):
    slug = "🐌-🐌-🐌"
    entry = mock.Mock(slug=slug)
    resource = factories.ResourceFactory(
        slug=slug,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
    )

    with mock.patch(
        "maven.feature_flags.bool_variation",
        return_value=True,
    ):
        index_resources.remove_contentful_article_from_index(entry)

    remove_mock.assert_called_with(resource)
    requests_mock.assert_called_with(
        "content_event",
        headers={"Content-type": "application/json"},
        json=[
            {
                "slug": slug,
                "event_type": "DELETE",
                "content_source": index_resources.ContentSource.CONTENTFUL,
                "learning_type": index_resources.LearningType.DEFAULT,
            }
        ],
        timeout=2,
    )


@mock.patch("utils.index_resources.index_article_from_contentful_entry")
@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("utils.index_resources.log")
def test_index_contentful_resource_no_entry(
    log_mock, client_class_mock, index_entry_mock, factories
):
    client_class_mock.return_value.get_article_entry_by_slug.return_value = None
    resource = factories.ResourceFactory()

    index_resources.index_contentful_resource(resource)

    log_mock.warn.assert_called_with(
        "Contentful entry not found when attempting to add to index",
        slug=resource.slug,
    )
    index_entry_mock.assert_not_called()


@mock.patch("utils.index_resources.index_article_from_contentful_entry")
@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("utils.index_resources.log")
def test_index_contentful_resource_error(
    log_mock, client_class_mock, index_entry_mock, factories
):
    error = Exception("🙅‍♀️")
    client_class_mock.side_effect = error
    resource = factories.ResourceFactory()

    index_resources.index_contentful_resource(resource)

    log_mock.error.assert_called_with(
        "Error adding resource to Elasticsearch index",
        error=error,
        slug=resource.slug,
    )
    index_entry_mock.assert_not_called()


@mock.patch("utils.index_resources.index_article_from_contentful_entry")
@mock.patch("learn.services.contentful.LibraryContentfulClient")
def test_index_contentful_resource(client_class_mock, index_entry_mock, factories):
    entry = mock.Mock()
    client_class_mock.return_value.get_article_entry_by_slug.return_value = entry
    resource = factories.ResourceFactory()

    index_resources.index_contentful_resource(resource)

    index_entry_mock.assert_called_with(entry)


@mock.patch("utils.index_resources.app_search_enabled", return_value=False)
def test_build_article_record_app_search_disabled(_):
    entry = mock.Mock()
    result = index_resources.build_article_record_from_contentful_entry(entry)
    assert result == {}


@mock.patch("utils.index_resources.app_search_enabled", return_value=True)
@mock.patch("utils.index_resources.log")
def test_build_article_record_no_resource(log_mock, _, factories):
    slug = "🐌-🐌-🐌"
    entry = mock.Mock(slug=slug)

    result = index_resources.build_article_record_from_contentful_entry(entry)

    assert result == {}
    log_mock.info.assert_called_with(
        "Resource not found or not eligible when attempting to add to index",
        slug=slug,
    )


@mock.patch("utils.index_resources.app_search_enabled", return_value=True)
@mock.patch("learn.utils.rich_text_utils.rich_text_to_plain_string_array")
@mock.patch("learn.models.image.Image.from_contentful_asset")
def test_build_article_record_success(img_mock, rich_to_plain_mock, _, factories):
    # Setup
    slug = "test-slug"
    title = "Test Title"
    entry = mock.Mock(slug=slug, title=title)
    resource = factories.ResourceFactory(
        slug=slug,
        tracks=["pregnancy"],
        tags=[factories.TagFactory.create()],
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),  # noqa
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
    )

    # Mock rich text conversion
    def side_effect(root_node, string_array):
        string_array += ["str1", "str2", "str3"]

    rich_to_plain_mock.side_effect = side_effect

    # Mock image
    img_mock.return_value = mock.Mock(description="img description")
    img_mock.return_value.asset_url.return_value = "u.rl/img.img"

    # Execute
    result = index_resources.build_article_record_from_contentful_entry(entry, resource)

    # Assert
    assert result == {
        "id": f"resource:{resource.id}",
        "raw_id": resource.id,
        "slug": resource.slug,
        "title": title,
        "body_content": "str1 str2 str3",
        "image_url": "u.rl/img.img",
        "image_description": "img description",
        "content_type": resource.content_type,
        "tracks": ["pregnancy"],
        "article_type": "rich_text",
    }


@mock.patch("utils.index_resources.app_search_enabled", return_value=True)
@mock.patch("learn.services.contentful.LibraryContentfulClient")
def test_build_article_record_from_contentful_resource_slugs_no_resources(
    client_class_mock, _, factories
):
    # Test with resource IDs that don't exist or aren't LIVE
    resources = [
        factories.ResourceFactory(
            contentful_status=migration.ContentfulMigrationStatus.IN_PROGRESS
        ),
        factories.ResourceFactory(
            contentful_status=migration.ContentfulMigrationStatus.NOT_STARTED
        ),
        # No status set (None)
        factories.ResourceFactory(contentful_status=None),
    ]
    resource_slugs = [r.slug for r in resources]
    result = index_resources.build_article_record_from_contentful_resource_slugs(
        resource_slugs
    )

    # Expect a dictionary with resource IDs as keys and empty dicts as values
    expected = {slug: {} for slug in resource_slugs}
    assert result == expected
    client_class_mock.assert_not_called()


@mock.patch("utils.index_resources.app_search_enabled", return_value=True)
@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("utils.index_resources.build_article_record_from_contentful_entry")
def test_build_article_record_from_contentful_resource_slugs_no_entry(
    build_record_mock, client_class_mock, _, factories
):
    # Create a LIVE resource
    resource = factories.ResourceFactory(
        contentful_status=migration.ContentfulMigrationStatus.LIVE
    )
    client_mock = mock.Mock()
    client_class_mock.return_value = client_mock
    client_mock.get_article_entry_by_slug.return_value = None

    result = index_resources.build_article_record_from_contentful_resource_slugs(
        [resource.slug]
    )

    assert result == {resource.slug: {}}
    build_record_mock.assert_not_called()


@mock.patch("utils.index_resources.app_search_enabled", return_value=True)
@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.utils.rich_text_utils.rich_text_to_plain_string_array")
@mock.patch("learn.models.image.Image.from_contentful_asset")
def test_build_article_record_from_contentful_resource_slugs_success(
    img_mock, rich_to_plain_mock, client_class_mock, _, factories
):
    # Setup test resources
    resources = [
        factories.ResourceFactory(
            slug=f"test-slug-{i}",
            tracks=["pregnancy"],
            tags=[factories.TagFactory.create()],
            published_at=datetime.datetime.now() - datetime.timedelta(days=1),  # noqa`
            contentful_status=migration.ContentfulMigrationStatus.LIVE,
        )
        for i in range(3)
    ]
    resource_slugs = [r.slug for r in resources]

    # Mock contentful client and entries
    client_mock = mock.Mock()
    client_class_mock.return_value = client_mock
    entries = [
        mock.Mock(slug=resource.slug, title=f"Test Title {i}")
        for i, resource in enumerate(resources)
    ]
    client_mock.get_article_entry_by_slug.side_effect = {
        resource.slug: entry for resource, entry in zip(resources, entries)
    }.get

    # Mock rich text conversion
    def side_effect(root_node, string_array):
        string_array += ["str1", "str2", "str3"]

    rich_to_plain_mock.side_effect = side_effect

    # Mock image
    img_mock.return_value = mock.Mock(description="img description")
    img_mock.return_value.asset_url.return_value = "u.rl/img.img"

    # Execute
    result = index_resources.build_article_record_from_contentful_resource_slugs(
        resource_slugs
    )

    # Assert
    assert len(result) == len(resources)
    for i, resource in enumerate(resources):
        expected_record = {
            "id": f"resource:{resource.id}",
            "raw_id": resource.id,
            "slug": resource.slug,
            "title": f"Test Title {i}",
            "body_content": "str1 str2 str3",
            "image_url": "u.rl/img.img",
            "image_description": "img description",
            "content_type": resource.content_type,
            "tracks": ["pregnancy"],
            "article_type": "rich_text",
        }
        assert result[str(resource.slug)] == expected_record

    # Verify contentful client calls
    assert client_mock.get_article_entry_by_slug.call_count == len(resources)
    for resource in resources:
        client_mock.get_article_entry_by_slug.assert_any_call(resource.slug)


@mock.patch("utils.index_resources.app_search_enabled", return_value=True)
@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("utils.index_resources.build_article_record_from_contentful_entry")
def test_build_article_record_from_contentful_resource_slugs_batch_handling(
    build_record_mock, client_class_mock, _, factories
):
    # Create more resources than the batch size (100)
    batch_size = 105
    resources = [
        factories.ResourceFactory(
            contentful_status=migration.ContentfulMigrationStatus.LIVE
        )
        for _ in range(batch_size)
    ]
    resource_slugs = [r.slug for r in resources]

    # Mock contentful client
    client_mock = mock.Mock()
    client_class_mock.return_value = client_mock
    entry_mock = mock.Mock()
    client_mock.get_article_entry_by_slug.return_value = entry_mock

    # Mock record building
    expected_record = {"id": "test_record"}
    build_record_mock.return_value = expected_record

    result = index_resources.build_article_record_from_contentful_resource_slugs(
        resource_slugs
    )

    # Should have processed all resources
    assert len(result) == batch_size
    assert all(r == expected_record for r in result.values())
    assert build_record_mock.call_count == batch_size
    assert client_mock.get_article_entry_by_slug.call_count == batch_size


@mock.patch("utils.index_resources.remove_html_tags")
@mock.patch("utils.index_resources.clean_resource_html")
def test_build_record_from_not_contentful_resource_success(
    clean_mock, remove_tags_mock, factories
):
    # Setup
    resource = factories.ResourceFactory(
        title="Test Title",
        slug="test-slug",
        tracks=["track1", "track2"],
    )
    resource.get_body_html = mock.Mock(return_value="<p>Test content</p>")
    clean_mock.return_value = "<p>Test content</p>"
    remove_tags_mock.return_value = "Test content"

    # Execute
    result = index_resources._build_record_from_not_contentful_resource(resource)

    # Assert
    assert result == {
        "id": f"resource:{resource.id}",
        "content_type": resource.content_type,
        "raw_id": resource.id,
        "slug": resource.slug,
        "title": resource.title,
        "body_content": "Test content\nTest content",
        "image_storage_key": resource.image and resource.image.storage_key,
        "tracks": ["track1", "track2"],
        "article_type": "html",
    }


def test_build_record_from_not_contentful_resource_error(factories):
    # Setup
    resource = factories.ResourceFactory()
    resource.get_body_html = mock.Mock(side_effect=Exception("Test error"))

    # Execute
    result = index_resources._build_record_from_not_contentful_resource(resource)

    # Assert
    assert result == {}


@mock.patch("utils.index_resources.remove_html_tags")
@mock.patch("utils.index_resources.clean_resource_html")
def test_build_record_from_not_contentful_resource_complex_html(
    clean_mock, remove_tags_mock, factories
):
    # Setup
    resource = factories.ResourceFactory()
    html_content = """
        <p>First paragraph</p>
        <br>
        <p>Second paragraph</p>
        <br/>
        <p>Third paragraph</p>
    """
    resource.get_body_html = mock.Mock(return_value=html_content)
    clean_mock.return_value = html_content
    remove_tags_mock.side_effect = (
        lambda x: x.strip().replace("<p>", "").replace("</p>", "")
    )

    # Execute
    result = index_resources._build_record_from_not_contentful_resource(resource)

    # Assert
    expected_content = "First paragraph\nSecond paragraph\nThird paragraph"
    assert result["body_content"] == expected_content


@mock.patch("utils.index_resources.remove_html_tags")
@mock.patch("utils.index_resources.clean_resource_html")
def test_build_record_from_not_contentful_resource_empty_fields(
    clean_mock, remove_tags_mock, factories
):
    # Setup
    resource = factories.ResourceFactory(
        title="",
        slug="test-slug",
        tracks=[],
    )
    resource.get_body_html = mock.Mock(return_value="")
    clean_mock.return_value = ""
    remove_tags_mock.return_value = ""

    # Execute
    result = index_resources._build_record_from_not_contentful_resource(resource)

    # Assert
    assert result == {
        "id": f"resource:{resource.id}",
        "content_type": resource.content_type,
        "raw_id": resource.id,
        "slug": "test-slug",
        "title": "",
        "body_content": "",
        "image_storage_key": resource.image and resource.image.storage_key,
        "tracks": [],
        "article_type": "html",
    }


@mock.patch("learn.services.course_service.CourseService")
def test_build_course_record_from_course_slugs(courses_svc_mock, mock_course):
    courses_svc_mock.return_value.get_values.return_value = {
        mock_course.slug: mock_course
    }

    result = index_resources.build_course_record_from_course_slugs([mock_course.slug])

    assert mock_course.slug in result

    course_json = result[mock_course.slug]

    assert course_json["id"] == f"course:{mock_course.id}"
    assert course_json["title"] == mock_course.title
    assert course_json["description"] == mock_course.description
    assert course_json["learning_type"] == "COURSE"
    assert course_json["chapters"] == [
        {"length_in_minutes": chapter.length_in_minutes}
        for chapter in mock_course.chapters
    ]


@mock.patch("utils.index_resources._fetch_event_and_tracks")
def test_build_virtual_event_record_from_event_ids(event_tracks_mock):
    stress_category = VirtualEventCategoryFactory.create(name="stress-and-anxiety")
    track_pregnancy = VirtualEventCategoryTrackFactory.create(
        category=stress_category, track_name="pregnancy"
    )
    track_postpartum = VirtualEventCategoryTrackFactory.create(
        category=stress_category, track_name="postpartum"
    )
    event = VirtualEventFactory.create(
        scheduled_start=datetime.datetime.utcnow() + datetime.timedelta(days=1),
        title="Don't be stressed!",
        virtual_event_category=stress_category,
    )

    event_tracks_mock.return_value = (
        event,
        stress_category,
        [track_pregnancy, track_postpartum],
    )

    result = index_resources.build_virtual_event_record_from_event_ids([event.id])

    assert event.id in result

    event_json = result[event.id]
    assert event_json["id"] == f"event:{event.id}"
    assert event_json["title"] == event.title
    assert event_json["description"] == event.description
    assert "pregnancy, postpartum" in event_json["body_content"]
    assert event_json["event_category"]["id"] == stress_category.id
    assert len(event_json["track_associations"]) == 2

    actual_track_pregnancy = event_json["track_associations"][0]
    assert actual_track_pregnancy["id"] == track_pregnancy.id
    assert (
        actual_track_pregnancy["availability_start_week"]
        == track_pregnancy.availability_start_week
    )
