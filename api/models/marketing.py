from __future__ import annotations

import datetime
import enum
import re
from typing import TYPE_CHECKING, Iterable, Optional
from urllib.parse import urlencode

import requests
from misaka import HtmlRenderer, Markdown
from slugify import slugify
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Interval,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import relationship

import configuration
from learn.models import migration
from learn.models.article_type import ArticleType
from learn.models.media_type import MediaType
from learn.models.migration import ContentfulMigrationStatus
from models import marketing
from models.base import ModelBase, StringJSONProperty, TimeLoggedModelBase, db
from utils.cache import redis_client
from utils.data import JSONAlchemy
from utils.log import logger

if TYPE_CHECKING:
    from models.tracks import TrackName
    from models.tracks.phase import TrackAndPhaseName

log = logger(__name__)

rndr = HtmlRenderer()
md = Markdown(rndr)

URL_REDIRECT_PATH_CAMPAIGN = {
    "maternity-signup": "maternity",
    "maven-maternity-signup": "maternitymp",
    "maven-maternity-benefit-signup": "mavenemployee",
    "maven-fertility-signup": "fertilityef",
    "maven-egg-freezing-signup": "maternityef",
}

INACTIVE_ORG_REDIRECT_URL = "https://get.mavenclinic.com/soon"
INACTIVE_ORG_REDIRECT_NOFORM_URL = "https://get.mavenclinic.com/comingsoon"


class TextCopy(TimeLoggedModelBase):
    __tablename__ = "text_copy"

    id = Column(Integer, primary_key=True)
    name = Column(String(191), nullable=False, unique=True)
    content = Column(Text)

    def __repr__(self) -> str:
        return f"<TextCopy[{self.id}]: {self.name} size={len(self.content)}>"  # type: ignore[arg-type] # Argument 1 to "len" has incompatible type "Optional[str]"; expected "Sized"

    __str__ = __repr__


class URLRedirectPath(TimeLoggedModelBase):
    __tablename__ = "url_redirect_path"

    id = Column(Integer, primary_key=True)
    path = Column(String(120), nullable=False)

    def __repr__(self) -> str:
        return f"<URLRedirectPath[{self.id}] path={self.path}>"

    __str__ = __repr__


class CapturePageType(str, enum.Enum):
    FORM = "FORM"
    NO_FORM = "NO_FORM"

    def __str__(self) -> str:
        return str(self.value)


class URLRedirect(TimeLoggedModelBase):
    __tablename__ = "url_redirect"

    path = Column(String(128), primary_key=True)
    dest_url_path_id = Column(ForeignKey("url_redirect_path.id"), nullable=False)
    dest_url_redirect_path = relationship("URLRedirectPath")
    dest_url_args = Column(JSONAlchemy(Text(1000)), default={})
    active = Column(Boolean, nullable=False, default=True)
    organization_id = Column(ForeignKey("organization.id"))
    organization = relationship("Organization")

    DEST_URL_ARG_NAMES = frozenset(
        (
            "install_source",
            "install_content",
            "install_campaign",
            "install_ad_unit",
            "verify",
            "utm_source",
            "utm_medium",
            "utm_campaign",
        )
    )

    def build_redirect_url(self, base_url):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        url_args = {}

        if self.organization and not self.organization.is_active:
            url = (
                INACTIVE_ORG_REDIRECT_URL
                if self.organization.capture_page_type == CapturePageType.FORM
                else INACTIVE_ORG_REDIRECT_NOFORM_URL
            )
        else:
            if campaign_path := URL_REDIRECT_PATH_CAMPAIGN.get(
                self.dest_url_redirect_path.path
            ):
                campaign = campaign_path
            else:
                campaign = self.dest_url_redirect_path.path

            url = f"{base_url}/maven-enrollment/{campaign}"

            if self.organization:
                url_args["organization_id"] = self.organization.id
            for k, v in self.dest_url_args.items():
                if v:
                    url_args[k] = v
            if url_args:
                url += f"?{urlencode(url_args)}"
        return url


class ResourceTypes(enum.Enum):
    ENTERPRISE = "ENTERPRISE"
    PRIVATE = "PRIVATE"


class ResourceContentTypes(enum.Enum):
    article = "Article"
    on_demand_class = "On-demand class"
    real_talk = "Real Talk"
    ask_a_practitioner = "Ask a Practitioner"
    connected_content = "Connected Content"
    curriculum_step = "Curriculum Step"  # sorta deprecated but they're still around


class LibraryContentTypes(enum.Enum):
    article = ResourceContentTypes.article.value
    real_talk = ResourceContentTypes.real_talk.value
    ask_a_practitioner = ResourceContentTypes.ask_a_practitioner.value

    quiz = "Quiz"


resource_organizations = db.Table(
    "resource_organizations",
    Column("organization_id", Integer, ForeignKey("organization.id"), primary_key=True),
    Column("resource_id", Integer, ForeignKey("resource.id"), primary_key=True),
)

# TODO: [Tracks] Remove this table in Phase 3 of Tracks migration
# DEPRECATION WARNING: this table is being deprecated for resource_tracks
resource_modules = db.Table(
    "resource_modules",
    Column("module_id", Integer, ForeignKey("module.id"), primary_key=True),
    Column("resource_id", Integer, ForeignKey("resource.id"), primary_key=True),
)

# TODO: [Tracks] Remove this table in Phase 3 of Tracks migration
# DEPRECATION WARNING: this table is being deprecated for resource_track_phases
resource_phases = db.Table(
    "resource_phases",
    Column("phase_id", Integer, ForeignKey("phase.id"), primary_key=True),
    Column("resource_id", Integer, ForeignKey("resource.id"), primary_key=True),
)

# TODO: [Tracks] Remove this table in Phase 3 of Tracks migration
# DEPRECATION WARNING: this table is being deprecated for resource_connected_content_track_phases
resource_connected_content_phases = db.Table(
    "resource_connected_content_phases",
    Column("phase_id", Integer, ForeignKey("phase.id"), primary_key=True),
    Column("resource_id", Integer, ForeignKey("resource.id"), primary_key=True),
)


class ResourceTrack(ModelBase):
    __tablename__ = "resource_tracks"

    resource_id = Column(Integer, ForeignKey("resource.id"), primary_key=True)
    track_name = Column(String, primary_key=True)

    resource = relationship("Resource")


class ResourceTrackPhase(ModelBase):
    __tablename__ = "resource_track_phases"

    resource_id = Column(Integer, ForeignKey("resource.id"), primary_key=True)
    track_name = Column(String, primary_key=True)
    phase_name = Column(String, primary_key=True)

    resource = relationship("Resource")


class ResourceConnectedContentTrackPhase(ModelBase):
    __tablename__ = "resource_connected_content_track_phases"

    resource_id = Column(Integer, ForeignKey("resource.id"), primary_key=True)
    track_name = Column(String, primary_key=True)
    phase_name = Column(String, primary_key=True)

    resource = relationship("Resource")


class ResourceConnectedContent(ModelBase):
    resource_id = Column(Integer, ForeignKey("resource.id"), primary_key=True)
    connected_content_field_id = Column(
        Integer, ForeignKey("connected_content_field.id"), primary_key=True
    )
    value = Column(Text)
    field = relationship("ConnectedContentField")


class ResourceOnDemandClass(ModelBase):
    __tablename__ = "resource_on_demand_class"
    resource_id = Column(Integer, ForeignKey("resource.id"), primary_key=True)
    instructor = Column(String(120), nullable=False)
    length = Column(Interval(), nullable=False)

    resource = relationship("Resource", uselist=False)

    def __repr__(self) -> str:
        return f"<ResourceOnDemandClass[{self.resource_id}]: {self.resource.title}>"


class Resource(TimeLoggedModelBase):
    __tablename__ = "resource"
    constraints = (UniqueConstraint("resource_type", "slug"),)

    id = Column(Integer, primary_key=True)
    # legacy_id == contentful_id, just for tracking - can be dropped later
    legacy_id = Column(String(128), nullable=True, unique=True)
    resource_type = Column(Enum(ResourceTypes), nullable=False)
    content_type = Column(String(128), nullable=False)
    contentful_status = Column(
        Enum(ContentfulMigrationStatus),
        default=ContentfulMigrationStatus.NOT_STARTED,
        nullable=False,
    )
    connected_content_type = Column(String(128))
    published_at = Column(DateTime, nullable=True)
    image_id = Column(ForeignKey("image.id"), nullable=True)
    body = Column(Text, nullable=False)
    title = Column(String(128), nullable=False)
    subhead = Column(String(255), nullable=True)
    slug = Column(String(128), nullable=False)
    json = Column(JSONAlchemy(Text), default={})
    webflow_url = Column(String(256), nullable=True)
    webflow_image_url = StringJSONProperty("webflow_image_url")
    tags = relationship("Tag", back_populates="resources", secondary="tags_resources")

    image = relationship("Image")
    allowed_modules = relationship(
        "Module", backref="allowed_resources", secondary=resource_modules
    )
    allowed_organizations = relationship(
        "Organization", backref="allowed_resources", secondary=resource_organizations
    )
    allowed_phases = relationship(
        "Phase", backref="allowed_resources", secondary=resource_phases
    )
    connected_content_phases = relationship(
        "Phase", secondary=resource_connected_content_phases
    )
    connected_content_fields = relationship(
        "ResourceConnectedContent", backref="resource"
    )

    allowed_tracks = relationship("ResourceTrack", cascade="all, delete-orphan")

    allowed_track_phases = relationship(
        "ResourceTrackPhase", cascade="all, delete-orphan"
    )

    connected_content_track_phases = relationship(
        "ResourceConnectedContentTrackPhase", cascade="all, delete-orphan"
    )

    _webflow_content = None

    on_demand_class_fields = relationship(
        "ResourceOnDemandClass", uselist=False, cascade="all, delete-orphan"
    )

    estimated_read_time_minutes: Optional[int] = None
    media_type: Optional[MediaType] = None

    @property
    def allowed_track_names(self) -> Iterable["TrackName"]:
        from models.tracks import TrackName

        return [TrackName(t.track_name) for t in self.allowed_tracks]

    @property
    def allowed_track_phase_names(self) -> Iterable["TrackAndPhaseName"]:
        from models.tracks.phase import TrackAndPhaseName

        return [
            TrackAndPhaseName(track_name=tp.track_name, phase_name=tp.phase_name)
            for tp in self.allowed_track_phases
        ]

    @property
    def connected_content_track_phase_names(self) -> Iterable["TrackAndPhaseName"]:
        from models.tracks.phase import TrackAndPhaseName

        return [
            TrackAndPhaseName(track_name=tp.track_name, phase_name=tp.phase_name)
            for tp in self.connected_content_track_phases
        ]

    @property
    def content_url(self) -> str:
        config = configuration.get_api_config()
        return f"{config.common.base_url}/resources/content/{self.content_type}/{self.slug}"

    @property
    def custom_url(self) -> str:
        config = configuration.get_api_config()
        return f"{config.common.base_url}/resources/custom/{self.id}"

    def generate_slug(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not self.slug:
            self.slug = slugify(self.title)
        return self.slug

    def pull_image_from_webflow(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # This has to be imported locally because `models.images` causes a circular
        # import otherwise
        from models.images import upload_and_save_image_from_url

        current_image_url = self.get_image_url()
        if self.image_id and current_image_url == self.webflow_image_url:
            # Don't do anything -- image URL has not changed since last pull
            return
        log.debug(
            "Pulling new resource image from webflow",
            resource=self,
            image_url=current_image_url,
        )
        image = upload_and_save_image_from_url(current_image_url)
        if image is not None:
            self.image = image
            self.webflow_image_url = current_image_url
            db.session.add(self)

    @property
    def webflow_content(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.webflow_url is None:
            return None
        elif self._webflow_content is None:
            r = requests.get(self.webflow_url, timeout=5)
            r.raise_for_status()
            # Webflow returns utf-8 encoded content but lacks charset=utf-8 in the header
            r.encoding = "utf-8"
            self._webflow_content = r.text
        return self._webflow_content

    def get_body_html(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        content = self.webflow_content
        if content is None:
            return md(self.body)
        else:
            m = re.search(r"<body[^>]*>(.*)</body>", content, flags=re.S)
            return m.group(1)  # type: ignore[union-attr] # Item "None" of "Optional[Match[str]]" has no attribute "group"

    def get_head_html(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        content = self.webflow_content
        if content is None:
            return None
        else:
            m = re.search(r"<head>(.*)</head>", content, flags=re.S)
            return m.group(1)  # type: ignore[union-attr] # Item "None" of "Optional[Match[str]]" has no attribute "group"

    def get_image_url(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        content = self.webflow_content
        if content is None:
            return None
        if self.content_type == ResourceContentTypes.on_demand_class.name:
            # returns the video tag's poster attribute (preview image) or the header image
            # the video tag can be removed once old webflow templates are no longer live
            if "<video" in content:
                regex = '<video[^>]*poster="([^"]+)"'
            else:
                regex = (
                    '<img [^>]*src="([^"]+)" [^>]*class="[^"]*video-img-header[^"]*"'
                )
        else:
            # Return the FIRST image in the page
            # TODO: use a class name to better specify which image to use
            regex = '<img[^>]*src="([^"]+)"'
        m = re.search(regex, content, flags=re.S)
        return m.group(1) if m else None

    def is_contentful_article_ish(self) -> bool:
        return (
            self.is_article_ish()
            and self.contentful_status == migration.ContentfulMigrationStatus.LIVE
        )

    def is_article_ish(self) -> bool:
        return self.content_type in [
            marketing.ResourceContentTypes.article.name,
            marketing.ResourceContentTypes.real_talk.name,
            marketing.ResourceContentTypes.ask_a_practitioner.name,
            marketing.ResourceContentTypes.curriculum_step.name,
        ]

    @classmethod
    def get_public_published_resource_by_slug(cls, url_slug: str) -> Resource:
        resource = (
            db.session.query(Resource)
            .filter(
                Resource.slug == url_slug,
                Resource.resource_type == ResourceTypes.ENTERPRISE,
                Resource.published_at <= datetime.datetime.utcnow(),
            )
            .one_or_none()
        )
        return resource

    @property
    def article_type(self) -> ArticleType:
        """Whether this article should be sourced from webflow/admin (html) or contentful (rich_text),
        including checking the feature flag"""
        return self.convert_contentful_status_str_to_article_type(
            self.contentful_status.value  # type: ignore[attr-defined] # "str" has no attribute "value"
        )

    @staticmethod
    def convert_contentful_status_str_to_article_type(
        contentful_status: str,
    ) -> ArticleType:
        if contentful_status == ContentfulMigrationStatus.LIVE.value:
            return ArticleType.RICH_TEXT

        return ArticleType.HTML


def remove_from_index(mapper, connect, target):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    from utils import index_resources

    index_resources.remove_from_index(target)


def update_index_if_needed(mapper, connect, target):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    from utils import index_resources

    # Connected content resources should not be indexed
    # Resources must be published to be searchable
    # Resources must have a track to be searchable
    if (
        (target.content_type == ResourceContentTypes.connected_content.name)
        or (not target.published_at)
        or (not target.published_at < datetime.datetime.now())
        or (not target.allowed_tracks)
    ):
        index_resources.remove_from_index(target)
    # Article-type resources must have a tag to be searchable
    elif target.content_type in [
        ResourceContentTypes.article.name,
        ResourceContentTypes.real_talk.name,
        ResourceContentTypes.ask_a_practitioner.name,
    ]:
        if target.tags:
            if target.contentful_status == ContentfulMigrationStatus.LIVE.value:
                index_resources.index_contentful_resource(target)
        else:
            index_resources.remove_from_index(target)


event.listen(Resource, "before_delete", remove_from_index)
event.listen(Resource, "before_update", update_index_if_needed)


class ConnectedContentField(ModelBase):
    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False)


def generate_slug(mapper, connect, target):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    target.generate_slug()


event.listen(Resource, "before_update", generate_slug)
event.listen(Resource, "before_insert", generate_slug)

tags_resources = db.Table(
    "tags_resources",
    Column("tag_id", Integer, ForeignKey("tag.id"), primary_key=True),
    Column("resource_id", Integer, ForeignKey("resource.id"), primary_key=True),
)

tags_posts = db.Table(
    "tags_posts",
    Column("tag_id", Integer, ForeignKey("tag.id"), primary_key=True),
    Column("post_id", Integer, ForeignKey("post.id"), primary_key=True),
)


class Tag(TimeLoggedModelBase):
    __tablename__ = "tag"

    id: int = Column(Integer, primary_key=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[int]", variable has type "int")
    name: str = Column(String(128), nullable=False, unique=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[str]", variable has type "str")
    display_name: str = Column(String(128), nullable=False)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[str]", variable has type "str")

    resources = relationship(
        "Resource",
        passive_deletes=True,
        back_populates="tags",
        secondary=tags_resources,
    )

    posts = relationship(
        "Post", passive_deletes=True, backref="tags", secondary=tags_posts
    )

    def __repr__(self) -> str:
        return f"<Tag[{self.id}]: {self.display_name}>"


class PopularTopic(TimeLoggedModelBase):
    __tablename__ = "popular_topics_per_track"
    id = Column(Integer, primary_key=True)
    track_name = Column(String(120), nullable=False)
    topic = Column(String(50), nullable=False)
    sort_order = Column(Integer, nullable=False)
    constraints = (UniqueConstraint("track_name", "topic"),)


class IosNonDeeplinkUrl(TimeLoggedModelBase):
    __tablename__ = "ios_non_deeplink_urls"

    url = Column(String(255), nullable=False, primary_key=True)

    CACHE_KEY = "ios_non_deeplink_urls"

    @classmethod
    def all(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        client, results = None, None
        try:
            client = redis_client()
            log.debug("Fetching ios non-deeplink urls from Redis")
            cached = client.smembers(cls.CACHE_KEY)
            results = [elem.decode("utf-8") for elem in cached]
        except Exception as e:
            log.error("Error fetching cached ios non-deeplink urls from Redis", error=e)

        if not results:
            log.debug("Fetching ios non-deeplink urls from db")
            results = [elem.url for elem in cls.query.all()]
            if client and results:
                log.debug("Caching ios non-deeplink urls")
                cls._cache_all(client, results)

        return results

    @classmethod
    def _cache_all(cls, client, urls):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            client.sadd(cls.CACHE_KEY, *urls)
            client.expire(cls.CACHE_KEY, 24 * 60 * 60)
        except Exception as e:
            log.error("Error storing ios non-deeplink urls in Redis", error=e)

    @classmethod
    def clear_cache(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        client = redis_client()
        try:
            client.delete(cls.CACHE_KEY)
        except Exception as e:
            log.error("Error clearing ios non-deeplink urls cache", error=e)
            raise e
