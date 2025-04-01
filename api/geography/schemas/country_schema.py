from typing import Any

from marshmallow import Schema, fields, post_dump


class CountrySchema(Schema):
    alpha_2 = fields.String(required=True)
    alpha_3 = fields.String(required=True)
    name = fields.String(required=True)
    numeric = fields.Integer(required=True)
    official_name = fields.String()
    common_name = fields.String()

    @post_dump
    def remove_none_values(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        data: dict[str, Any],
        **kwargs,
    ) -> dict[str, Any]:
        return {key: value for key, value in data.items() if value}
