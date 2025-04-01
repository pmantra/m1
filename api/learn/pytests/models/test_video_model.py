from unittest import mock

import pytest

from learn.models.media_type import MediaType
from learn.models.video import Video
from learn.pytests.test_utils import create_contentful_asset_mock


@pytest.fixture
def mock_contentful_related_article():
    article_fields = {
        "title": "5 ways your partner can help you prepare for labor",
        "slug": "5-ways-your-partner-can-help-you-prepare-for-labor",
        "heroImage": {
            "sys": {"type": "Link", "linkType": "Asset", "id": "5YxqfZHb5Ovdcjv7Eo677j"}
        },
    }
    article = mock.Mock(**article_fields)
    article.fields.return_value = article_fields

    hero_image_fields = {
        "title": "GettyImages-1473370619",
        "description": "Pregnant couple holding hands.",
        "file": {
            "url": "//images.ctfassets.net/rxuqq62yis9z/5YxqfZHb5Ovdcjv7Eo677j/d7d4d224d7a7bde371c5e033f23a4912/GettyImages-1473370619.jpg",
            "details": {"size": 4766379, "image": {"width": 6439, "height": 3593}},
            "fileName": "GettyImages-1473370619.jpg",
            "contentType": "image/jpeg",
        },
    }
    article.hero_image = create_contentful_asset_mock(hero_image_fields)

    article.content_type.id = "article"
    return article


@pytest.fixture
def mock_contentful_video(mock_contentful_related_article, mock_contentful_course):
    video_fields = {
        "title": "3 exercises to prepare for labor and and birth",
        "slug": "3-exercises-to-prepare-for-labor-and-and-birth",
        "image": {
            "sys": {"type": "Link", "linkType": "Asset", "id": "I07enTjMfthr1m3ZEkFJP"}
        },
        "video": {
            "sys": {"type": "Link", "linkType": "Entry", "id": "8qN7G7ECityP1Ijvx09Nl"}
        },
        "related": [
            {
                "sys": {
                    "type": "Link",
                    "linkType": "Entry",
                    "id": "9c920eade03f197b2cf1be0ec9dc2e57",
                }
            },
            {
                "sys": {
                    "type": "Link",
                    "linkType": "Entry",
                    "id": "aeb65826e47d9ff953a0e6a7c22844fe",
                }
            },
        ],
    }
    video = mock.Mock(**video_fields)
    image_file_fields = {
        "title": "GettyImages-1456192111-min",
        "description": "Person sitting in a cafe and interested in what they're reading on their laptop.",
        "file": {
            "url": "//images.ctfassets.net/rxuqq62yis9z/I07enTjMfthr1m3ZEkFJP/2c381a3b7943714228b4ef9bdca90589/GettyImages-1456192111-min.jpg",
            "details": {"size": 4470450, "image": {"width": 7983, "height": 4000}},
            "fileName": "GettyImages-1456192111-min.jpg",
            "contentType": "image/jpeg",
        },
    }
    video.image = create_contentful_asset_mock(image_file_fields)

    embedded_video_fields = {
        "name": "tips-from-a-specialist-3-exercises-to-prepare-for-labor-and-birth",
        "video_link": "https://player.vimeo.com/progressive_redirect/download/910537788/rendition/1080p/3_exercises_to_prepare_for_labor_and_birth_product_final%20%281080p%29.mp4?loc=external&signature=d0c6dc74881aa5c1aa8dd83810c4a3d9591c717d60942218ead9f322900be7af",
        "thumbnail": {
            "sys": {"type": "Link", "linkType": "Asset", "id": "3CFlx1GhKdVkv5iCorJfUE"}
        },
        "captions": {
            "sys": {"type": "Link", "linkType": "Asset", "id": "UsvZIErBHycZlLHlWrnKW"}
        },
    }
    embedded_video = mock.Mock(**embedded_video_fields)

    captions_file_attributes = {
        "title": "3 exercises to prepare for labor and birth product",
        "description": "",
        "file": {
            "url": "//assets.ctfassets.net/rxuqq62yis9z/UsvZIErBHycZlLHlWrnKW/d0bb91a9d78df8d93e719c1ad067b35a/3_exercises_to_prepare_for_labor_and_birth_product.vtt",
            "details": {"size": 4552},
            "fileName": "3 exercises to prepare for labor and birth_product.vtt",
            "contentType": "text/vtt",
        },
    }
    embedded_video.captions = create_contentful_asset_mock(captions_file_attributes)

    video.video = embedded_video
    video.related = [mock_contentful_course, mock_contentful_related_article]
    return video


@mock.patch("learn.models.video.ReadTimeService")
def test_from_contentful_entry(mock_read_time_service, mock_contentful_video):
    mock_read_time_service.return_value.get_value.return_value = 7
    video = Video.from_contentful_entry(mock_contentful_video)

    assert video.slug == mock_contentful_video.slug
    assert video.title == mock_contentful_video.title
    assert (
        video.captions_url
        == "https:" + mock_contentful_video.video.captions.file["url"]
    )
    assert video.video_url == mock_contentful_video.video.video_link
    assert len(video.related) == 2

    assert video.related[0].title == "Breastfeeding, pumping, and formula"
    assert video.related[0].related_content_type == MediaType.COURSE
    assert video.related[0].chapter_count == 10

    assert (
        video.related[1].title == "5 ways your partner can help you prepare for labor"
    )
    assert video.related[1].related_content_type == MediaType.ARTICLE
    assert video.related[1].estimated_read_time == 7
