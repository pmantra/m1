from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional, Type

from marshmallow import ValidationError, fields, pre_dump
from sqlalchemy.orm.exc import NoResultFound

from authn.models.user import User
from authz.models.roles import ROLES
from models.forum import Post
from models.profiles import Category, PractitionerProfile
from storage.connection import db
from views.schemas.base import (
    BooleanWithDefault,
    CSVIntegerFieldV3,
    IntegerWithDefaultV3,
    MavenDateTimeV3,
    MavenSchemaV3,
    PaginableArgsSchemaV3,
    PaginableOutputSchemaV3,
    PractitionerProfileSchemaV3,
    SchemaV3,
    StringWithDefaultV3,
    UserProfilesSchemaV3,
    UserRoleFieldV3,
    UserSchemaV3,
)


class PostGETCategoryField(fields.Field):
    def _deserialize(
        self,
        value: str,
        attr: Optional[str],
        data: Optional[Mapping[str, Any]],
        **kwargs: Any,
    ) -> list[str]:
        vals = []
        for v in value.split(","):
            try:
                db.session.query(Category).filter(Category.name == v).one()
                vals.append(v)
            except NoResultFound:
                raise ValidationError(f"{v} is not an allowed category!")
        return vals


class PostCategoryField(fields.Field):
    def _deserialize(
        self,
        value: str | list,
        attr: Optional[str],
        data: Optional[Mapping[str, Any]],
        **kwargs: Any,
    ) -> list[str]:
        vals = []

        if isinstance(value, str):
            cats = value.split(",")
        elif isinstance(value, list):
            # when loading from cache, we have the output of serialize below...
            # so we already have the list of names
            cats = value

        for cat_name in cats:
            try:
                vals.append(
                    db.session.query(Category).filter(Category.name == cat_name).one()
                )
            except NoResultFound:
                raise ValidationError(f"{cat_name} is not an allowed category!")
        return vals

    def _serialize(
        self, value: list[Any], attr: Optional[str], obj: Any, **kwargs: Any
    ) -> list[str]:
        _ret = []

        for s in value:
            if isinstance(s, str):
                _ret.append(s)
            else:
                _ret.append(s.name)

        return _ret


def validate_depth(value: str | int) -> str | int:
    if value in ("0", "1", 0, 1):
        return value
    raise ValidationError("Bad depth!")


class PostsGetSchema(PaginableArgsSchemaV3):
    parent_ids = CSVIntegerFieldV3(required=False)
    ids = CSVIntegerFieldV3(required=False)
    order_by = fields.String(load_default="")
    author_role = UserRoleFieldV3()
    author_ids = CSVIntegerFieldV3()
    depth = fields.Integer(validate=validate_depth, load_default=None)
    categories = PostGETCategoryField()
    sticky = fields.String()
    keywords = fields.String(load_default="")
    title_keywords = fields.String(load_default="")
    body_keywords = fields.String(load_default="")
    include_parent = fields.Boolean(required=False, load_default=False)
    recommended_for_id = fields.Integer(
        load_default=None
    )  # Deprecated: still sent by some iOS versions


class _ReplyCountsSchema(SchemaV3):
    practitioners = fields.Integer(dump_default=0)
    members = fields.Integer(dump_default=0)


class PostCategorySchema(SchemaV3):
    id = fields.Integer()
    name = fields.String()
    display_name = fields.String()


class ForumPractitionerProfileSchema(PractitionerProfileSchemaV3):
    class Meta:
        exclude = ("state", "next_availability")


class ForumProfilesSchema(UserProfilesSchemaV3):
    def get_practitioner_profile(
        self,
        profiles: dict[str, PractitionerProfile],
        profile_schema: (
            Type[PractitionerProfileSchemaV3] | None
        ) = ForumPractitionerProfileSchema,
    ) -> dict[str, Any]:
        return super().get_practitioner_profile(
            profiles,
            profile_schema=profile_schema,
        )


class ForumUserSchema(UserSchemaV3):
    def get_profiles(
        self,
        user: User,
        profiles_schema: (Type[UserProfilesSchemaV3] | None) = ForumProfilesSchema,
    ) -> dict[str, Any] | None:
        return super().get_profiles(
            user,
            profiles_schema=profiles_schema,
        )


class PostSchema(MavenSchemaV3):
    @pre_dump()
    def convert_string_timestamps(
        self, data: Post | dict, **kwargs: Any
    ) -> Post | dict:
        if isinstance(data, Post):
            # MavenDateTimeV3 will properly handle the datetime if this is a Post object
            return data
        if isinstance(data, dict) and isinstance(data.get("created_at"), str):
            # If the created_at attribute is a string from the cache, we need to handle it here
            data["created_at"] = datetime.strptime(
                data["created_at"], "%Y-%m-%dT%H:%M:%S"
            )

        return data

    id = fields.Integer()
    title = StringWithDefaultV3(dump_default="")
    body = fields.String(required=True)
    created_at = MavenDateTimeV3()
    parent_id = IntegerWithDefaultV3(dump_default=0)
    parent = fields.Method(serialize="get_parent_post")
    author = fields.Method(serialize="get_author")
    categories = PostCategoryField(required=False)
    has_bookmarked = fields.Method(serialize="get_has_bookmarked")
    reply_counts = fields.Method(serialize="get_reply_counts")
    anonymous = BooleanWithDefault(dump_default=True)
    bookmarks_count = fields.Integer()
    category_objects = fields.Method(serialize="get_category_objects")
    sticky_priority = fields.String()
    recaptcha_token = fields.String(dump_default="")
    # These vote fields are not used, yet are required by clients.
    # Setting to constants since the values don't matter.
    net_votes = fields.Integer(dump_default=0)
    has_voted = BooleanWithDefault(dump_default=False)

    def get_reply_counts(self, obj: Post | dict) -> dict:
        schema = _ReplyCountsSchema()
        if isinstance(obj, dict):
            data = self.context.get("reply_counts", {}).get(obj["id"], {})
            return schema.dump(data)
        else:
            data = self.context.get("reply_counts", {}).get(obj.id, {})
            return schema.dump(data)

    def get_category_objects(self, obj: Post | dict) -> list[dict]:
        if isinstance(obj, dict):
            return obj.get("category_objects", [])
        else:
            return PostCategorySchema().dump(obj.categories, many=True)

    def get_author(self, obj: Post | dict) -> Optional[dict]:
        if isinstance(obj, dict):
            author = obj["author"] if (obj["anonymous"] is False) else None
        else:
            author = obj.author if (obj.anonymous is False) else None

        if author:
            schema = ForumUserSchema(
                only=[
                    "id",
                    "first_name",
                    "middle_name",
                    "last_name",
                    "name",
                    "username",
                    "role",
                    "image_url",
                    "image_id",
                    "avatar_url",
                    "profiles",
                ]
            )
            schema.context["user"] = self.context.get("user")
            schema.context["include_profile"] = True
            data = schema.dump(author)

            # partially hide practitioner last name in public view
            if not self.context.get("user") and data["role"] == ROLES.practitioner:
                last_name_initial = data["last_name"][:1]
                data["name"] = data["name"].replace(
                    data["last_name"], last_name_initial
                )
                data["last_name"] = last_name_initial

            # empty out member names as we display username in forum
            if data["role"] == ROLES.member:
                data["first_name"] = ""
                data["middle_name"] = ""
                data["last_name"] = ""
                data["name"] = ""
                if isinstance(author, dict):
                    data["username"] = author["username"]
                else:
                    data["username"] = author.username

            return data
        return None

    def get_has_bookmarked(self, obj: Post | dict) -> bool:
        if self.context.get("user"):
            if isinstance(obj, dict):
                return obj["has_bookmarked"]
            else:
                return obj.user_has_bookmarked(self.context["user"])
        else:
            return False

    def get_parent_post(self, obj: Post | dict) -> Optional[dict]:
        if self.context.get("include_parent"):
            if isinstance(obj, dict):
                if obj["parent_id"]:
                    return obj["parent"]
            else:
                if obj.parent_id:
                    return PostSchema().dump(obj.parent)
        return None


class PostsSchema(PaginableOutputSchemaV3):
    data = fields.Method(serialize="get_posts")  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Method", base class "PaginableOutputSchemaV3" defined the type as "RawWithDefaultV3")

    def get_posts(self, obj: dict) -> list[dict]:
        schema = PostSchema()
        schema.context = self.context
        return schema.dump(obj["data"], many=True)
