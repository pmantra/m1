from __future__ import annotations

import os

SVG_BUCKET_NAME = os.environ.get("SVG_BUCKET_NAME", "maven-dev-svg")


class SVGImageMixin:
    def image_url(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, bucket_name: str = SVG_BUCKET_NAME, attr_name="image_id"
    ) -> str | None:
        image_id = None

        if hasattr(self, attr_name):
            image_id = getattr(self, attr_name)

        if image_id:
            return f"https://storage.googleapis.com/{bucket_name}/{image_id}"

        return None
