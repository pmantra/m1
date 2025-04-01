import factory
from factory.alchemy import SQLAlchemyModelFactory

from conftest import BaseMeta
from models.marketing import (
    ConnectedContentField,
    ResourceConnectedContent,
    ResourceConnectedContentTrackPhase,
)
from models.tracks import TrackName
from pytests.factories import ResourceFactory


class ConnectedContentFieldFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ConnectedContentField

    name = factory.Faker("text")


class ResourceConnectedContentFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ResourceConnectedContent

    resource = factory.SubFactory(ResourceFactory)
    field = factory.SubFactory(ConnectedContentFieldFactory)
    value = factory.Faker("text")


class ResourceConnectedContentTrackPhaseFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ResourceConnectedContentTrackPhase

    resource = factory.SubFactory(ResourceFactory)
    track_name = factory.Faker("random_element", elements=[*TrackName])
    phase_name = "week-1"
