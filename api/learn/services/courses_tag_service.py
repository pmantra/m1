import json
from typing import Any, Dict, List, Optional

from learn.models import course
from learn.services import contentful_caching_service, course_service, read_time_service
from utils import log

logger = log.logger(__name__)


class CoursesTagService(contentful_caching_service.ContentfulCachingService[List[str]]):
    def __init__(self, preview: bool = False, user_facing: bool = True):
        super().__init__(preview=preview, user_facing=user_facing)
        self.course_service = course_service.CourseService(
            preview=preview, user_facing=user_facing
        )
        self.read_time_service = read_time_service.ReadTimeService(
            preview=preview, user_facing=user_facing
        )

    def get_courses_for_tag(
        self, tag: str, limit: Optional[int] = None
    ) -> List[course.Course]:
        courses = []
        course_slugs = self.get_value(tag)
        if course_slugs is not None:
            if limit:
                course_slugs = course_slugs[0:limit]
            courses = list(
                self.course_service.get_values(identifier_values=course_slugs).values()
            )
        return courses

    def _get_values_from_contentful(  # type: ignore[no-untyped-def,override] # Signature of "_get_values_from_contentful" incompatible with supertype "ContentfulCachingService"
        self, tags: List[str], **kwargs
    ) -> Dict[str, List[str]]:
        # Not limiting, so cache entry could serve an all courses page
        course_entries = self.contentful_client.get_courses_by_tags(tags)
        course_slugs_by_tag = {tag: [] for tag in tags}

        for course_entry in course_entries:
            # even though this is a protected field, it's how Contentful recommends accessing tags:
            # https://github.com/contentful/contentful.py?tab=readme-ov-file#accessing-tags
            for tag in course_entry._metadata["tags"]:
                if tag.id in course_slugs_by_tag:
                    course_slugs_by_tag[tag.id].append(course_entry.slug)

        return course_slugs_by_tag

    def _get_cache_key(self, identifier_value: str, **kwargs: Any) -> str:
        # Here the value is a tag
        return f"courses:{identifier_value}"

    @staticmethod
    def _serialize_value(value: List[str]) -> str:
        return json.dumps(value)

    @staticmethod
    def _deserialize_value(value_str: str) -> List[str]:
        return json.loads(value_str)

    def clear_cache(self) -> None:
        self.remove_keys_from_cache_by_pattern("courses:*")
