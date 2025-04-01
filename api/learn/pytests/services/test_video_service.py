import pytest

from learn.models.article import RelatedReadWithReadTime
from learn.models.article_type import ArticleType
from learn.models.course import RelatedCourseWithChapterCount
from learn.models.image import Image
from learn.models.video import Video
from learn.services.video_service import VideoService


@pytest.fixture
def video():
    return Video(
        title="Video title",
        slug="video-slug",
        image=Image(url="/link/to/image", description="image description"),
        video_url="/link/to/video",
        captions_url="/link/to/captions",
        related=[
            RelatedReadWithReadTime(
                title="Related article title",
                slug="related-article-slug",
                thumbnail=Image(url="/link/to/image", description="image description"),
                estimated_read_time=7,
                type=ArticleType.RICH_TEXT,
            ),
            RelatedCourseWithChapterCount(
                title="Related course title",
                slug="related-course-slug",
                thumbnail=Image(url="/link/to/image", description="image description"),
                chapter_count=9,
            ),
        ],
    )


def test_video_serializes_and_deserializes(video):
    video_json = VideoService._serialize_value(video)
    assert VideoService._deserialize_value(video_json) == video
