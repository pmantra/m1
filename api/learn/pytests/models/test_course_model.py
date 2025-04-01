from learn.models.course import RelatedCourseWithChapterCount
from learn.models.media_type import MediaType


class TestRelatedCourseWithChapterCount:
    def test_from_contentful_entry(self, mock_contentful_course):
        related_course_with_chapter_count: RelatedCourseWithChapterCount = (
            RelatedCourseWithChapterCount.from_contentful_entry(mock_contentful_course)
        )
        assert related_course_with_chapter_count.slug == mock_contentful_course.slug
        assert related_course_with_chapter_count.title == mock_contentful_course.title
        assert related_course_with_chapter_count.chapter_count == 10
        assert (
            related_course_with_chapter_count.related_content_type == MediaType.COURSE
        )
        assert (
            related_course_with_chapter_count.thumbnail.description
            == mock_contentful_course.image.description
        )
        assert (
            related_course_with_chapter_count.thumbnail.url
            == "https:" + mock_contentful_course.image.file["url"]
        )
