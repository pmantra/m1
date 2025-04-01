import dataclasses
import json
from typing import Dict, List

from sqlalchemy import and_

from learn.models import course_factory
from learn.models.course import Course
from learn.models.resource_interaction import ResourceInteraction, ResourceType
from learn.services import contentful_caching_service
from storage.connection import db
from utils import log

logger = log.logger(__name__)


class CourseService(contentful_caching_service.ContentfulCachingService[Course]):
    @staticmethod
    def populate_viewed_at(courses: List[Course], user_id: int) -> List[Course]:
        if len(courses) == 0:
            return courses

        resource_interactions = {
            resource_interaction.slug: resource_interaction
            for resource_interaction in db.session.query(ResourceInteraction)
            .filter(
                and_(
                    ResourceInteraction.user_id == user_id,
                    ResourceInteraction.resource_type == ResourceType.ARTICLE,
                    ResourceInteraction.slug.in_(
                        [
                            chapter.slug
                            for course in courses
                            for chapter in course.chapters
                        ]
                    ),
                )
            )
            .all()
        }

        for course in courses:
            for chapter in course.chapters:
                if resource_interaction := resource_interactions.get(chapter.slug):
                    chapter.viewed_at = resource_interaction.resource_viewed_at

        return courses

    def _get_values_from_contentful(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, identifier_values: List[str], **kwargs
    ) -> Dict[str, Course]:
        course_entries = self.contentful_client.get_courses_by_slug(identifier_values)
        return {
            course_entry.slug: course_factory.from_contentful_entry(
                course_entry, self.preview
            )
            for course_entry in course_entries
        }

    def _get_cache_key(self, identifier_value: str, **kwargs: str) -> str:
        return f"course:{identifier_value}"

    @staticmethod
    def _serialize_value(value: Course) -> str:
        return json.dumps(dataclasses.asdict(value))

    @staticmethod
    def _deserialize_value(value_str: str) -> Course:
        course_dict = json.loads(value_str)
        return course_factory.from_dict(course_dict)
