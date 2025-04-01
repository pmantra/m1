from typing import Any, Dict, Optional

import contentful

from learn.models import article, course, image, media_type, related_content
from learn.services import article_service
from learn.services.contentful import ContentfulContentType


def from_contentful_entry(
    entry: contentful.Entry, preview: bool = False, user_facing: bool = False
) -> Optional[related_content.RelatedContent]:
    content_type = ContentfulContentType(entry.content_type.id)
    if content_type in [
        ContentfulContentType.ARTICLE,
        ContentfulContentType.NON_CONTENTFUL_ARTICLE,
    ]:
        return article_service.ArticleService(
            preview=preview, user_facing=user_facing
        ).parse_as_related_read(entry)
    elif content_type == ContentfulContentType.COURSE:
        return course.RelatedCourse.from_contentful_entry(entry)
    raise ValueError(f"Unsupported content type {content_type.value}.")


def from_dict(d: Dict[str, Any]) -> related_content.RelatedContent:  # type: ignore[return] # Missing return statement
    related_content_type: media_type.MediaType = media_type.MediaType(
        d.pop("related_content_type")
    )
    d["thumbnail"] = image.Image(**d["thumbnail"])
    if related_content_type == media_type.MediaType.ARTICLE:
        return article.RelatedRead(**d)
    elif related_content_type == ContentfulContentType.COURSE:
        d["chapters"] = [
            course.RelatedCourseChapter.from_dict(chapter_dict)
            for chapter_dict in d["chapters"]
        ]
        return course.RelatedCourse(**d)
