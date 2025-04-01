import dataclasses
from typing import Dict, Optional

import contentful

from learn.utils.contentful_utils import get_url


@dataclasses.dataclass
class Image:
    url: str
    description: Optional[str] = None

    @classmethod
    def from_contentful_asset(cls, asset: contentful.Asset):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # Sometimes it is an asset object, sometimes it is already the url???
        if asset is None:
            return None

        # TODO: aspect ratio?
        # https://www.contentful.com/developers/docs/concepts/images/
        # https://www.contentful.com/developers/docs/references/images-api/#/reference/changing-formats/avif
        url = get_url(asset)
        return cls(url=url, description=asset.fields().get("description"))

    @staticmethod
    def from_dict(d: Dict[str, str]) -> "Image":
        return Image(url=d["url"], description=d.get("description"))

    # Mimicking the models.images.Image class's method
    def asset_url(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, height: Optional[int] = None, width: Optional[int] = None, **_kwargs: dict
    ):
        if width and height:
            # https://www.contentful.com/developers/docs/references/images-api/#/reference/resizing-&-cropping/change-the-resizing-behavior
            # fit=fill resizes the image to the dimensions, cropping if necessary
            return f"{self.url}?w={width}&h={height}&fit=fill"
        return self.url
