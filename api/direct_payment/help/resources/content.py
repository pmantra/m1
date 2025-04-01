import enum

from flask import request
from flask_restful import Resource
from httpproblem import Problem

from common.services.api import AuthenticatedResource, UnauthenticatedResource
from direct_payment.clinic.resources.clinic_auth import ClinicAuthorizedResource
from direct_payment.help.schemas.article import ArticleSchema
from direct_payment.help.schemas.topics import TopicSchema
from direct_payment.help.services import contentful
from learn.models.article_type import ArticleType
from utils.log import logger

log = logger(__name__)


class MMBCategory(str, enum.Enum):
    BENEFITS_EXPERIENCE = "Benefits Experience"
    FERTILITY_CLINIC_PORTAL = "Fertility Clinic Portal"
    GENERAL = "General"


class BaseHelpArticleTopicsResource(Resource):
    def __init__(self, category, resource_class):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.category = category
        self.resource_class = resource_class

    def get_contentful_client(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return contentful.MMBContentfulClient(preview=False, user_facing=True)

    def fetch_topics(self, contentful_client):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return contentful_client.get_help_topics_for_category(self.category)

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            contentful_client = self.get_contentful_client()
            topics = self.fetch_topics(contentful_client)
            if topics:
                schema = TopicSchema(many=True)
                result = schema.dump(topics)
                return {"data": result}
            else:
                raise Problem(404, detail="Topics not found.")
        except Exception as e:
            log.warning(
                "Error fetching topics from contentful",
                exc_info=True,
                error=e,
            )
            raise e


class BenefitsExperienceHelpArticleTopicsResource(
    BaseHelpArticleTopicsResource, UnauthenticatedResource
):
    def __init__(self) -> None:
        super().__init__(MMBCategory.BENEFITS_EXPERIENCE, UnauthenticatedResource)


class FertilityClinicPortalHelpArticleTopicsResource(
    BaseHelpArticleTopicsResource, ClinicAuthorizedResource
):
    def __init__(self) -> None:
        super().__init__(MMBCategory.FERTILITY_CLINIC_PORTAL, ClinicAuthorizedResource)


class BaseHelpArticleResource(Resource):
    def __init__(self, category, resource_class):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.category = category
        self.resource_class = resource_class

    def get_contentful_client(self, preview):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        client = contentful.MMBContentfulClient(preview=preview, user_facing=True)
        return client

    def fetch_article(self, contentful_client, url_slug):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return contentful_client.get_article_by_slug(url_slug, self.category)

    def get(self, url_slug):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        preview = bool(request.args.get("preview"))
        try:
            contentful_client = self.get_contentful_client(preview)
            article = self.fetch_article(contentful_client, url_slug)
            if article:
                schema = ArticleSchema()
                article["type"] = ArticleType.RICH_TEXT

                return schema.dump(article)
            else:
                raise Problem(404, detail="Article not found.")

        except Exception as e:
            log.warning(
                "Error fetching article from contentful",
                exc_info=True,
                slug=url_slug,
                preview=preview,
                error=e,
            )
            raise e


class FertilityClinicPortalHelpArticleResource(
    BaseHelpArticleResource, ClinicAuthorizedResource
):
    def __init__(self) -> None:
        super().__init__(MMBCategory.FERTILITY_CLINIC_PORTAL, ClinicAuthorizedResource)


class MMBGeneralArticleResource(BaseHelpArticleResource, AuthenticatedResource):
    def __init__(self) -> None:
        super().__init__(MMBCategory.GENERAL, AuthenticatedResource)


class BenefitsExperienceHelpArticleResource(
    BaseHelpArticleResource, UnauthenticatedResource
):
    def __init__(self) -> None:
        super().__init__(MMBCategory.BENEFITS_EXPERIENCE, UnauthenticatedResource)
