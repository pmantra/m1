from __future__ import annotations

from typing import Any, Mapping

from marshmallow import fields
from marshmallow_v1 import fields as fields_v1
from maven import feature_flags

from authn.models.user import User
from l10n.db_strings.translate import TranslateDBFields
from models.verticals_and_specialties import Vertical
from utils.launchdarkly import user_context
from utils.log import logger
from views.schemas.base import PractitionerProfileSchemaV3, V2VerticalSchemaV3
from views.schemas.common import PractitionerProfileSchema

log = logger(__name__)


def _should_localize_fields(user: User | None) -> bool:
    return bool(
        user
        and user.is_member
        and feature_flags.bool_variation(
            "release-care-discovery-provider-field-localization",
            user_context(user),
            default=False,
        )
    )


def _serialize_vertical_name_with_translation(
    user: User | None, value: list[Vertical]
) -> list[str]:
    if not value:
        return []
    localize_provider_fields = _should_localize_fields(user)
    if not localize_provider_fields:
        return [v.marketing_name for v in value]

    ret = []
    for vertical in value:
        en_value = vertical.marketing_name
        if vertical.slug:
            translated_attr = TranslateDBFields().get_translated_vertical(
                vertical.slug, "name", en_value
            )
            ret.append(translated_attr)
        else:
            log.error(f"Missing slug during translation! {vertical}")
            ret.append(en_value)
    return ret


class TranslatedVerticalsV3(fields.Field):
    array_attr = "name"

    """
    This class translates an array of Verticals with attributes "marketing_name" and "slug" into an array
    of strings which are the translated names based on slug lookup. It does not deserialize.
    
    Based loosely on views.schemas.base._ArrayofAttrV3
    """

    def _deserialize(
        self,
        value: list[str],
        attr: str | None,
        data: Mapping[str, Any] | None,
        **kwargs: Any,
    ) -> list[Vertical]:
        raise NotImplementedError("This schema only supports serialization")

    def _serialize(
        self, value: list[Vertical], attr: str | None, obj: Any, **kwargs: Any
    ) -> list[str]:
        user: User | None = self.context.get("user")
        return _serialize_vertical_name_with_translation(user, value)


class TranslatedV2VerticalSchemaV3(V2VerticalSchemaV3):
    name = fields.Method(serialize="get_name")  # type: ignore[assignment]
    pluralized_display_name = fields.Method(serialize="get_pluralized_display_name")  # type: ignore[assignment]
    description = fields.Method(serialize="get_description")  # type: ignore[assignment]
    long_description = fields.Method(serialize="get_long_description")  # type: ignore[assignment]

    def get_maybe_translated_field_helper(self, obj: Vertical, attr: str) -> str:
        if not obj:
            return ""

        user: User | None = self.context.get("user")
        localize_provider_fields = _should_localize_fields(user)
        untranslated_value = getattr(obj, attr)
        if not localize_provider_fields:
            return untranslated_value
        if not obj.slug:
            return untranslated_value
        return TranslateDBFields().get_translated_vertical(
            obj.slug, attr, untranslated_value
        )

    def get_name(self, obj: Vertical) -> str:
        return self.get_maybe_translated_field_helper(obj, "name")

    def get_pluralized_display_name(self, obj: Vertical) -> str:
        return self.get_maybe_translated_field_helper(obj, "pluralized_display_name")

    def get_description(self, obj: Vertical) -> str:
        return self.get_maybe_translated_field_helper(obj, "description")

    def get_long_description(self, obj: Vertical) -> str:
        return self.get_maybe_translated_field_helper(obj, "long_description")


class TranslatedPractitionerProfileSchemaV3(PractitionerProfileSchemaV3):
    """
    This class translates the name of the vertical based on the slug. It does not support deserialization.
    In principle, we could translate specialty and language in the same way, but we need to first make
    sure that the clients use those fields for display only.
    """

    verticals = TranslatedVerticalsV3(required=False)  # type: ignore[assignment]


# The below classes are copies of the above ones, except for marshmallow v1 schemas.
# We'd like to delete these as soon as /channels/{id}/status endpoint migrates onto v3.
class TranslatedVerticalsV1(fields_v1.Field):
    def _deserialize(self, value: list[str]):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        raise NotImplementedError("This schema only supports serialization")

    def _serialize(self, value: list[Vertical], attr: str, obj: Any) -> list[str]:  # type: ignore[no-untyped-def]
        user: User | None = self.context.get("user")
        return _serialize_vertical_name_with_translation(user, value)


class TranslatedPractitionerProfileSchemaV1(PractitionerProfileSchema):
    verticals = TranslatedVerticalsV1(required=False)
