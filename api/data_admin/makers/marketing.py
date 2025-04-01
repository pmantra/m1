import pymysql
import sqlalchemy
from flask import flash
from marshmallow_v1 import fields

from data_admin.maker_base import _MakerBase
from models.marketing import PopularTopic, TextCopy
from models.tracks import TrackLifecycleError, TrackName
from storage.connection import db
from utils.exceptions import ProgramLifecycleError
from views.schemas.common import MavenSchema


class PopularTopicSchema(MavenSchema):
    topic = fields.String()
    track_name = fields.Enum(choices=[t.value for t in TrackName])
    sort_order = fields.Integer()


class TextCopyMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            text_copy = TextCopy(name=spec.get("name"), content=spec.get("content"))
            db.session.add(text_copy)
        except (
            pymysql.err.IntegrityError,
            sqlalchemy.exc.IntegrityError,
            TrackLifecycleError,
            # TODO: [Tracks] Phase 3 - drop this error
            ProgramLifecycleError,
        ) as e:
            flash(str(e), "error")
            raise e
        return text_copy


class PopularTopicMaker(_MakerBase):
    spec_class = PopularTopicSchema(strict=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "PopularTopicSchema", base class "_MakerBase" defined the type as "None")

    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        spec_data = self.spec_class.load(spec).data  # type: ignore[has-type] # Cannot determine type of "spec_class"
        popular_topic = PopularTopic(
            topic=spec_data.get("topic"),
            track_name=spec_data.get("track_name"),
            sort_order=spec_data.get("sort_order"),
        )

        db.session.add(popular_topic)

        return popular_topic
