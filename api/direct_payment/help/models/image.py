import dataclasses
from typing import Optional

import contentful


@dataclasses.dataclass
class Image:
    url: str
    description: Optional[str] = None

    @classmethod
    def from_contentful_asset(cls, asset: contentful.Asset):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if asset is None:
            return None
        url = asset.url()
        if url.startswith("//"):
            url = "https:" + url
        return cls(url=url, description=asset.fields().get("description"))
