import enum

from sqlalchemy.sql import schema, sqltypes

from models import base


# yes this is similar to Contentful content type
# it's also similar to lots of other things
# but it's distinct and we shouldn't conflate them
class ResourceType(enum.Enum):
    ARTICLE = enum.auto()
    ON_DEMAND_CLASS = enum.auto()


class ResourceInteraction(base.TimeLoggedModelBase):
    __tablename__ = "resource_interactions"

    user_id = schema.Column(
        sqltypes.Integer, schema.ForeignKey("user.id"), nullable=False, primary_key=True
    )
    resource_type = schema.Column(
        sqltypes.Enum(ResourceType), nullable=False, primary_key=True
    )
    slug = schema.Column(sqltypes.String(128), nullable=False, primary_key=True)
    resource_viewed_at = schema.Column(sqltypes.DateTime)
