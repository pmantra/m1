import dataclasses
from typing import Optional

from learn.models import image, media_type


@dataclasses.dataclass
class RelatedContent:
    title: str
    thumbnail: Optional[image.Image]
    slug: str
    related_content_type: media_type.MediaType = dataclasses.field(init=False)
