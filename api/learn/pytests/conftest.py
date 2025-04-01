from unittest import mock

import pytest

from learn.models import article_type
from learn.models import image as contentful_image
from learn.models.article import RelatedRead
from learn.pytests.test_utils import create_contentful_asset_mock


@pytest.fixture
def mock_contentful_course():
    course_fields = {
        "slug": "breastfeeding-pumping-and-formula",
        "title": "Breastfeeding, pumping, and formula",
        "image": {
            "sys": {"type": "Link", "linkType": "Asset", "id": "5xZ3OhmuKttkmy0FxDw6Kv"}
        },
        "description": "Not sure how you’ll feed baby? Knowing your options is a great way to begin! Learn how to breast-, bottle-, or combo-feed like a pro in one course.",
        "chapters": [
            {
                "sys": {
                    "type": "Link",
                    "linkType": "Entry",
                    "id": "1WJe9vgudsKdvZly8salJ7",
                }
            },
            {
                "sys": {
                    "type": "Link",
                    "linkType": "Entry",
                    "id": "2MWFqZg55H74clw3lBMSSp",
                }
            },
            {
                "sys": {
                    "type": "Link",
                    "linkType": "Entry",
                    "id": "5pExsNYARerg7h9aegfYJx",
                }
            },
            {
                "sys": {
                    "type": "Link",
                    "linkType": "Entry",
                    "id": "1Wbq4S046oiRzzLghy8li5",
                }
            },
            {
                "sys": {
                    "type": "Link",
                    "linkType": "Entry",
                    "id": "4IJV4iMivY7Woo0z00a84K",
                }
            },
            {
                "sys": {
                    "type": "Link",
                    "linkType": "Entry",
                    "id": "4Q8vEneDgDk5xTqKE3r8xo",
                }
            },
            {
                "sys": {
                    "type": "Link",
                    "linkType": "Entry",
                    "id": "3QsFftOgO6fsl4wUrCV3OP",
                }
            },
            {
                "sys": {
                    "type": "Link",
                    "linkType": "Entry",
                    "id": "5JnERAw1e6Hs2HXYrLse8X",
                }
            },
            {
                "sys": {
                    "type": "Link",
                    "linkType": "Entry",
                    "id": "77iassMgvimb0PuZJqe29n",
                }
            },
            {
                "sys": {
                    "type": "Link",
                    "linkType": "Entry",
                    "id": "3t8nMDakg2KBLTt3TdDqj3",
                }
            },
        ],
    }
    course = mock.Mock(**course_fields)

    image_fields = {
        "title": "GettyImages-930504668",
        "description": "Parent bottle feeding their baby.",
        "file": {
            "url": "//images.ctfassets.net/rxuqq62yis9z/5xZ3OhmuKttkmy0FxDw6Kv/20536a9e59e8e84a89c87b83b08527ce/GettyImages-1129631725.jpg",
            "details": {"size": 13516195, "image": {"width": 6000, "height": 4000}},
            "fileName": "GettyImages-1129631725.jpg",
            "contentType": "image/jpeg",
        },
    }

    course.image = create_contentful_asset_mock(image_fields)
    course.content_type.id = "course"
    return course


@pytest.fixture
def image_1():
    return contentful_image.Image(
        url="cold-weather-thumbnail.jpg", description="Cold Weather Thumbnail"
    )


@pytest.fixture
def image_2():
    return contentful_image.Image(
        url="bringing-baby-home-thumbnail.jpg",
        description="Bringing Baby Home Thumbnail",
    )


@pytest.fixture
def image_3():
    return contentful_image.Image(
        url="hot-weather-thumbnail.jpg", description="Hot Weather Thumbnail"
    )


@pytest.fixture
def title_1():
    return "4 Safety Tips for Dressing Your Baby in Cold Weather"


@pytest.fixture
def title_2():
    return "Must-Have Items for Bringing Baby Home: It's Way Less Than You Think"


@pytest.fixture
def title_3():
    return "Dressing Baby for Hot Weather"


@pytest.fixture
def thumbnail_service_mock(image_1, image_2, image_3):

    # Set up mock to return thumbnails for the expected slugs
    mock_dict = {
        "4-safety-tips-for-dressing-your-baby-in-cold-weather": image_1,
        "must-have-items-for-bringing-baby-home-its-way-less-than-you-think": image_2,
        "dressing-baby-for-hot-weather": image_3,
    }

    def side_effect(arg):
        return mock_dict[arg]

    with mock.patch(
        "learn.services.predicted_related_reads_service.ArticleThumbnailService"
    ) as thumbnail_service_mock:
        # Set up mock to return thumbnails for the expected slugs
        thumbnail_service_mock().get_thumbnail_by_slug.side_effect = side_effect
        yield thumbnail_service_mock


@pytest.fixture
def title_service_mock(title_1, title_2, title_3):
    mock_dict = {
        "4-safety-tips-for-dressing-your-baby-in-cold-weather": title_1,
        "must-have-items-for-bringing-baby-home-its-way-less-than-you-think": title_2,
        "dressing-baby-for-hot-weather": title_3,
    }

    def side_effect(arg):
        return mock_dict[arg]

    # Set up mock to return titles for the expected slugs
    with mock.patch(
        "learn.services.predicted_related_reads_service.LocalizedArticleTitleService"
    ) as title_service_mock:
        title_service_mock().get_value.side_effect = side_effect
        yield title_service_mock


@pytest.fixture
def related_reads_1(title_1, image_1):
    return RelatedRead(
        slug="4-safety-tips-for-dressing-your-baby-in-cold-weather",
        title=title_1,
        thumbnail=image_1,
        type=article_type.ArticleType.RICH_TEXT,
    )


@pytest.fixture
def related_reads_2(title_2, image_2):
    return RelatedRead(
        slug="must-have-items-for-bringing-baby-home-its-way-less-than-you-think",
        title=title_2,
        thumbnail=image_2,
        type=article_type.ArticleType.RICH_TEXT,
    )


@pytest.fixture
def related_reads_3(title_3, image_3):
    return RelatedRead(
        slug="dressing-baby-for-hot-weather",
        title=title_3,
        thumbnail=image_3,
        type=article_type.ArticleType.RICH_TEXT,
    )


@pytest.fixture
def related_reads_list(related_reads_1, related_reads_2, related_reads_3):
    return [related_reads_1, related_reads_2, related_reads_3]
