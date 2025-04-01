from typing import Any, Dict, List

from contentful import Entry

from learn.models import image, media_type, related_content_factory
from learn.models.course import Course, CourseCallout, CourseChapter, CourseChapterBase
from learn.models.course_member_status import MemberStatus
from learn.services.contentful import ContentfulContentType
from learn.services.read_time_service import ReadTimeService


def from_contentful_entry(
    course_entry: Entry, preview: bool = False, user_facing: bool = False
) -> Course:
    course = Course(
        id=course_entry.id,
        slug=course_entry.slug,
        title=course_entry.title,
        image=image.Image.from_contentful_asset(course_entry.image),
        description=course_entry.description,
        chapters=[
            CourseChapter.from_contentful_entry(chapter)
            for chapter in course_entry.chapters
        ],
        callout=CourseCallout.from_contentful_entry(course_entry.course_callout)
        if hasattr(course_entry, "course_callout")
        else None,
        related=[
            related_content
            for related_entry in getattr(course_entry, "related", [])
            if (
                related_content := related_content_factory.from_contentful_entry(
                    related_entry, preview, user_facing
                )
            )
        ],
    )

    all_chapters: List[CourseChapterBase] = [
        *course.chapters,
        *[
            chapter
            for chapters in [
                related_content.chapters  # type: ignore[attr-defined] # "RelatedContent" has no attribute "chapters"
                for related_content in course.related
                if related_content.related_content_type == media_type.MediaType.COURSE
            ]
            for chapter in chapters
        ],
    ]

    all_chapter_entries = {
        entry.content.slug: entry.content
        for entry in [
            *course_entry.chapters,
            *[
                chapter
                for chapters in [
                    related_content.chapters
                    for related_content in getattr(course_entry, "related", [])
                    if related_content.content_type.id == ContentfulContentType.COURSE
                ]
                for chapter in chapters
            ],
        ]
    }

    read_time_service = ReadTimeService(preview=preview, user_facing=user_facing)

    estimated_read_times_minutes = {
        slug: read_time_service.calculate_read_time(entry)
        for slug, entry in all_chapter_entries.items()
    }
    read_time_service.try_to_save_values_in_cache(estimated_read_times_minutes)

    for chapter in all_chapters:
        if (
            estimated_read_times_minutes.get(chapter.slug)
            and estimated_read_times_minutes.get(chapter.slug) < 0
        ):
            chapter.media_type = media_type.MediaType.VIDEO
        else:
            chapter.media_type = media_type.MediaType.ARTICLE
            chapter.length_in_minutes = estimated_read_times_minutes.get(chapter.slug)

    return course


def from_dict(d: Dict[str, Any]) -> Course:
    member_status = d.pop("member_status")
    d["image"] = image.Image(**d["image"])
    d["chapters"] = [
        CourseChapter.from_dict(chapter_dict) for chapter_dict in d["chapters"]
    ]
    d["callout"] = CourseCallout.from_dict(d["callout"]) if d["callout"] else None
    d["related"] = [
        related_content_factory.from_dict(related_dict)
        for related_dict in d.pop("related")
    ]
    course = Course(**d)
    course.member_status = MemberStatus(member_status) if member_status else None
    return course
