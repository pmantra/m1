from dataclasses import dataclass, field
from typing import Union

import contentful
from typing_extensions import Self

from learn.models.article import RelatedRead, RelatedReadWithReadTime
from learn.models.course import RelatedCourseWithChapterCount
from learn.models.image import Image
from learn.services.contentful import ContentfulContentType
from learn.services.read_time_service import ReadTimeService
from learn.utils.contentful_utils import get_url


@dataclass
class Video:
    slug: str
    title: str
    image: Image
    video_url: str
    captions_url: str
    related: list[
        Union[RelatedReadWithReadTime, RelatedCourseWithChapterCount]
    ] = field(default_factory=list)

    @classmethod
    def from_contentful_entry(cls, entry: contentful.Entry) -> Self:
        video = cls(
            slug=entry.slug,
            title=entry.title,
            image=Image.from_contentful_asset(entry.image),
            video_url=entry.video.video_link,
            captions_url=get_url(entry.video.captions),
            related=[
                related_content
                for related_entry in getattr(entry, "related", [])
                if (related_content := Video.from_related(related_entry))
            ],
        )
        return video

    @classmethod
    def from_related(
        cls, entry: contentful.Entry
    ) -> Union[RelatedReadWithReadTime, RelatedCourseWithChapterCount]:
        content_type = ContentfulContentType(entry.content_type.id)
        if content_type == ContentfulContentType.ARTICLE:
            related_read = RelatedRead.from_contentful(entry)
            estimated_read_times_minutes = ReadTimeService().get_value(
                identifier_value=related_read.slug
            )
            related_read_with_read_time = RelatedReadWithReadTime(
                title=related_read.title,
                thumbnail=related_read.thumbnail,
                slug=related_read.slug,
                type=related_read.type,
                estimated_read_time=estimated_read_times_minutes,
            )
            return related_read_with_read_time
        elif content_type == ContentfulContentType.COURSE:
            return RelatedCourseWithChapterCount.from_contentful_entry(entry)
        raise ValueError(f"Unsupported content type {content_type.value}.")

    @classmethod
    def from_dict(cls, video_dict: dict) -> Self:
        video_dict["image"] = Image(**video_dict["image"])
        related: list[
            Union[RelatedReadWithReadTime, RelatedCourseWithChapterCount]
        ] = []
        for related_entry in video_dict["related"]:
            related_entry["thumbnail"] = Image(**related_entry["thumbnail"])
            if related_entry["related_content_type"] == "article":
                related_entry.pop("related_content_type")
                related.append(RelatedReadWithReadTime(**related_entry))
            elif related_entry["related_content_type"] == "course":
                related_entry.pop("related_content_type")
                related.append(RelatedCourseWithChapterCount(**related_entry))
        video_dict["related"] = related
        return cls(**video_dict)
