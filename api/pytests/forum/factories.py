import factory
from factory.alchemy import SQLAlchemyModelFactory

from conftest import BaseMeta
from models import forum
from pytests.factories import EnterpriseUserFactory


class PostFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = forum.Post

    author = factory.SubFactory(EnterpriseUserFactory)
    author_id = factory.SelfAttribute("author.id")
    body = "i am a post"
