import marshmallow
from marshmallow import fields

from learn.models.image import Image


class CTA(marshmallow.Schema):
    class Meta:
        unknown = marshmallow.EXCLUDE

    text = fields.String(allow_none=True)
    url = fields.Url(relative=True, allow_none=True)


class Banner(marshmallow.Schema):
    class Meta:
        unknown = marshmallow.EXCLUDE

    title = fields.String(required=True)
    body = fields.String(required=True)
    image = fields.Url(required=True, relative=True)
    cta = fields.Nested(CTA, required=True)
    secondary_cta = fields.Nested(CTA, allow_none=True)

    @marshmallow.pre_load
    def pre_load(self, data, **_):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if "cta" not in data:
            data["cta"] = dict(text=data["cta_text"], url=data["cta_url"])
        if "secondary_cta" not in data:
            data["secondary_cta"] = (
                dict(
                    text=data.get("secondary_cta_text", None),
                    url=data.get("secondary_cta_url", None),
                )
                if "secondary_cta_text" in data or "secondary_cta_url" in data
                else None
            )
        if type(data["image"]) is not str:
            data["image"] = Image.from_contentful_asset(data["image"]).asset_url()
        return data
