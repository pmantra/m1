import dataclasses
import datetime
import json
from typing import Any, Dict, List, Optional

import contentful
from typing_extensions import Self

from learn.models import image, related_content
from learn.models.course_member_status import CourseMemberStatus, MemberStatus
from learn.models.media_type import MediaType
from maven_json import maven_json_encoder
from views.models.cta import CTA


@dataclasses.dataclass
class CourseChapterBase:
    slug: str
    media_type: MediaType = dataclasses.field(init=False, default=None)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "MediaType")
    length_in_minutes: Optional[int] = dataclasses.field(init=False, default=None)


@dataclasses.dataclass
class RelatedCourseChapter(CourseChapterBase):
    @staticmethod
    def from_contentful_entry(entry: contentful.Entry) -> "RelatedCourseChapter":
        return RelatedCourseChapter(
            slug=entry.content.slug,
        )

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "RelatedCourseChapter":
        media_type = d.pop("media_type")
        media_type = MediaType(media_type) if media_type else None
        length_in_minutes = d.pop("length_in_minutes")
        related_course_chapter = RelatedCourseChapter(**d)
        related_course_chapter.media_type = media_type
        related_course_chapter.length_in_minutes = length_in_minutes
        return related_course_chapter


@dataclasses.dataclass
class RelatedCourse(related_content.RelatedContent):
    related_content_type: MediaType = dataclasses.field(
        init=False, default=MediaType.COURSE
    )
    chapters: List[RelatedCourseChapter]

    @staticmethod
    def from_contentful_entry(entry: contentful.Entry) -> "RelatedCourse":
        return RelatedCourse(
            title=entry.title,
            slug=entry.slug,
            thumbnail=image.Image.from_contentful_asset(entry.image),
            chapters=[
                RelatedCourseChapter.from_contentful_entry(related_course_chapter_entry)
                for related_course_chapter_entry in entry.chapters
            ],
        )


@dataclasses.dataclass
class RelatedCourseWithChapterCount(related_content.RelatedContent):
    related_content_type: MediaType = dataclasses.field(
        init=False, default=MediaType.COURSE
    )
    chapter_count: int

    @classmethod
    def from_contentful_entry(cls, entry: contentful.Entry) -> Self:
        return cls(
            title=entry.title,
            slug=entry.slug,
            thumbnail=image.Image.from_contentful_asset(entry.image),
            chapter_count=len(entry.chapters),
        )


@dataclasses.dataclass
class CourseChapter(CourseChapterBase):
    title: str
    description: str
    image: image.Image
    viewed_at: Optional[datetime.datetime] = dataclasses.field(init=False, default=None)

    @staticmethod
    def from_contentful_entry(entry: contentful.Entry):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return CourseChapter(
            slug=entry.content.slug,
            title=entry.title,
            description=entry.description,
            image=image.Image.from_contentful_asset(entry.content.hero_image),
        )

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "CourseChapter":
        media_type = d.pop("media_type")
        media_type = MediaType(media_type) if media_type else None
        viewed_at: Optional[datetime.datetime]
        length_in_minutes = d.pop("length_in_minutes")
        viewed_at = d.pop("viewed_at")
        d["image"] = image.Image(**d["image"])
        course_chapter = CourseChapter(**d)
        course_chapter.media_type = media_type
        course_chapter.length_in_minutes = length_in_minutes
        course_chapter.viewed_at = viewed_at
        return course_chapter


@dataclasses.dataclass
class CourseCallout:
    __slots__ = ("title", "cta")
    title: str
    cta: CTA

    @staticmethod
    def from_contentful_entry(entry: contentful.Entry):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return CourseCallout(
            title=entry.title,
            cta=CTA(text=entry.cta_text, url=entry.cta_url),
        )

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "CourseCallout":
        d["cta"] = CTA(**d["cta"])
        return CourseCallout(**d)


@dataclasses.dataclass
class Course:
    id: str
    slug: str
    title: str
    image: image.Image
    description: str
    callout: Optional[CourseCallout]
    chapters: List[CourseChapter]
    related: List[related_content.RelatedContent]
    member_status: Optional[MemberStatus] = dataclasses.field(init=False, default=None)

    def set_status(self, member_status_record: Optional[CourseMemberStatus]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if member_status_record:
            self.member_status = member_status_record.status  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", variable has type "Optional[MemberStatus]")
        else:
            self.member_status = MemberStatus.NOT_STARTED.value  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", variable has type "Optional[MemberStatus]")

    def to_response_dict(self) -> Dict[str, Any]:
        return json.loads(
            json.dumps(
                dataclasses.asdict(self), cls=maven_json_encoder.MavenJSONEncoder
            )
        )
