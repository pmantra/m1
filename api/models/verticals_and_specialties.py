import datetime
from typing import TYPE_CHECKING, Iterable

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    bindparam,
)
from sqlalchemy.ext import baked
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import backref, relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from l10n.db_strings.translate import TranslateDBFields
from models import base
from models.base import db
from models.mixins import SVGImageMixin
from models.tracks.client_track import TrackModifiers
from provider_matching.models.in_state_matching import (
    VerticalInStateMatching,
    VerticalInStateMatchState,
)
from utils.data import JSONAlchemy
from utils.log import logger

# These will cause a circular imports at run-time but are valid for static type-checking
if TYPE_CHECKING:
    from models.tracks import TrackName
    from models.tracks.member_track import MemberTrack  # noqa: F401


log = logger(__name__)

CX_VERTICAL_NAME = "Care Advocate"
BIRTH_PLANNING_VERTICAL_NAME = "Birth planning"
DOULA_ONLY_VERTICALS = frozenset(["doula and childbirth educator", "care advocate"])

CX_FERTILITY_CARE_COACHING_SLUG = "fertility_care_coaching"
CX_PREGNANCY_CARE_COACHING_SLUG = "pregnancy_care_coaching"


def is_cx_vertical_name(name) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Checks whether a literal string or SQLAlchemy expression matches the CX
    vertical name.
    """
    if isinstance(name, str):
        return name == "Care Advocate" or name == "Care Coordinator"
    return name.in_(("Care Advocate", "Care Coordinator"))


def exclude_vertical_name_from_query(name: InstrumentedAttribute):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return name.in_((CX_VERTICAL_NAME, BIRTH_PLANNING_VERTICAL_NAME))


def is_cx_coaching_speciality_slug(slug: InstrumentedAttribute) -> bool:
    return slug in (CX_FERTILITY_CARE_COACHING_SLUG, CX_PREGNANCY_CARE_COACHING_SLUG)


vertical_groupings = db.Table(
    "vertical_groupings",
    Column("vertical_id", Integer, ForeignKey("vertical.id")),
    Column("vertical_group_id", Integer, ForeignKey("vertical_group.id")),
    UniqueConstraint("vertical_id", "vertical_group_id"),
)

vertical_grouping_versions = db.Table(
    "vertical_grouping_versions",
    Column(
        "vertical_group_version_id", Integer, ForeignKey("vertical_group_version.id")
    ),
    Column("vertical_group_id", Integer, ForeignKey("vertical_group.id")),
    UniqueConstraint("vertical_group_version_id", "vertical_group_id"),
)

vertical_group_specialties = db.Table(
    "vertical_group_specialties",
    Column("vertical_group_id", Integer, ForeignKey("vertical_group.id")),
    Column("specialty_id", Integer, ForeignKey("specialty.id")),
    UniqueConstraint("vertical_group_id", "specialty_id"),
)

specialty_specialty_keywords = db.Table(
    "specialty_specialty_keywords",
    Column("specialty_id", Integer, ForeignKey("specialty.id")),
    Column("specialty_keyword_id", Integer, ForeignKey("specialty_keyword.id")),
    UniqueConstraint("specialty_id", "specialty_keyword_id"),
)


class Specialty(base.ModelBase, SVGImageMixin):
    __tablename__ = "specialty"

    id = Column(Integer, primary_key=True)
    name = Column(String(70), nullable=False, unique=True)
    image_id = Column(String(70), nullable=True)
    ordering_weight = Column(Integer, nullable=True)
    slug = Column(String(128), unique=True)

    vertical_groups = relationship(
        "VerticalGroup",
        backref=backref("specialties", order_by=ordering_weight.desc()),
        secondary=vertical_group_specialties,
    )

    searchable_localized_data = Column(JSONAlchemy(Text), default={})

    def __repr__(self) -> str:
        return f"<Specialty[{self.id}] [{self.name}]>"

    __str__ = __repr__


class SpecialtyKeyword(base.ModelBase):
    __tablename__ = "specialty_keyword"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False, unique=True)

    specialties = relationship(
        "Specialty",
        backref=backref("specialty_keywords", order_by=id.asc()),
        secondary=specialty_specialty_keywords,
    )

    def __repr__(self) -> str:
        return f"<SpecialtyKeyword[{self.id}] [{self.name}]>"


class VerticalGroupVersion(base.ModelBase):
    __tablename__ = "vertical_group_version"

    id = Column(Integer, primary_key=True)
    name = Column(String(70), nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"<VerticalGroupVersion [{self.name}]>"

    __str__ = __repr__


class VerticalGroup(base.ModelBase, SVGImageMixin):
    __tablename__ = "vertical_group"

    id = Column(Integer, primary_key=True)
    name = Column(String(70), nullable=False, unique=True)
    title = Column(String(70), nullable=True)
    image_id = Column(String(70), nullable=True)
    hero_image_id = Column(Integer, ForeignKey("image.id"))
    hero_image = relationship("Image")
    ordering_weight = Column(Integer, nullable=True)
    description = Column(String(255), nullable=True)

    versions = relationship(
        "VerticalGroupVersion",
        backref="verticals",
        secondary=vertical_grouping_versions,
    )

    allowed_tracks = relationship("VerticalGroupTrack", cascade="all, delete-orphan")

    @property
    def allowed_track_names(self) -> Iterable["TrackName"]:
        """
        Returns the names of the tracks for which this is the onboarding assessment lifecycle.
        """
        from models.tracks import TrackName

        return [TrackName(t.track_name) for t in self.allowed_tracks]

    def __repr__(self) -> str:
        return f"<VerticalGroup [{self.name}]>"

    __str__ = __repr__


class Vertical(base.ModelBase):
    __tablename__ = "vertical"

    id = Column(Integer, primary_key=True)
    name = Column(String(70), nullable=False, unique=True)
    description = Column(String(255))
    long_description = Column(String(300))
    display_name = Column(String(70), nullable=True)
    pluralized_display_name = Column(String(70), nullable=False)

    filter_by_state = Column(Boolean, nullable=False, default=False)
    can_prescribe = Column(Boolean, nullable=False, default=False)

    promo_start = Column(DateTime, nullable=True)
    promo_end = Column(DateTime, nullable=True)

    deleted_at = Column(DateTime, nullable=True)

    groups = relationship(
        "VerticalGroup", backref="verticals", secondary=vertical_groupings
    )

    products = Column(JSONAlchemy(Text(1000)), default=list)

    in_state_matching_states = relationship(
        "State",
        secondary=VerticalInStateMatchState.__tablename__,
    )

    in_state_matching = relationship(VerticalInStateMatching, back_populates="vertical")
    in_state_matching_subdivisions = association_proxy(
        "in_state_matching",
        "subdivision_code",
        creator=lambda x: VerticalInStateMatching(subdivision_code=x),
    )
    promote_messaging = Column(Boolean, nullable=False, default=False)
    slug = Column(String(128), unique=True)

    searchable_localized_data = Column(JSONAlchemy(Text), default={})

    region = Column(String(128), nullable=True)

    vertical_access = relationship("VerticalAccessByTrack", back_populates="vertical")

    def __repr__(self) -> str:
        return f"<Vertical [{self.name}] (Filter by state: {self.filter_by_state})>"

    def __str__(self) -> str:
        return f"{self.name} (Filter by state: {self.filter_by_state})"

    @property
    def marketing_name(self) -> str:
        return self.display_name or self.name

    def get_marketing_name(self, should_localize: bool = False) -> str:
        # wrap this in a flag which decides whether to localize or not
        if should_localize and self.slug:
            translations = TranslateDBFields()
            translated_display_name = translations.get_translated_vertical(
                self.slug, "display_name", ""
            )

            return translated_display_name or translations.get_translated_vertical(
                self.slug, "name", self.marketing_name
            )
        return self.marketing_name

    @property
    def promo_active(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.promo_start is None or self.promo_end is None:
            return
        now = datetime.datetime.utcnow()
        return self.promo_start <= now <= self.promo_end

    def has_access_with_track_modifiers(
        self, track_modifiers: list[TrackModifiers], client_track_id: int
    ) -> bool:
        return any(
            access_by_track.client_track_id == client_track_id
            and access_by_track.track_modifiers is not None
            and any(
                modifier in access_by_track.track_modifiers
                for modifier in track_modifiers
            )
            for access_by_track in self.vertical_access
        )


class VerticalGroupTrack(base.ModelBase):
    __tablename__ = "tracks_vertical_groups"

    track_name = Column(String, primary_key=True)
    vertical_group_id = Column(
        Integer, ForeignKey("vertical_group.id"), primary_key=True
    )

    vertical_group = relationship("VerticalGroup")


bakery = baked.bakery()  # type: ignore[call-arg,func-returns-value] # Missing positional argument "initial_fn" in call to "__call__" of "Bakery" #type: ignore[func-returns-value] # Function does not return a value (it only ever returns None) #type: ignore[func-returns-value] # Function does not return a value (it only ever returns None)


class VerticalAccessByTrack(base.TimeLoggedModelBase):
    __tablename__ = "vertical_access_by_track"

    client_track_id = Column(Integer, primary_key=True)
    vertical_id = Column(Integer, ForeignKey("vertical.id"), primary_key=True)
    track_modifiers = Column(Text, nullable=True)
    vertical = relationship("Vertical", back_populates="vertical_access")


def get_vertical_groups_for_track(track_name: str) -> Iterable["VerticalGroup"]:
    query: baked.BakedQuery = bakery(
        lambda session: session.query(VerticalGroup)
        .join(
            VerticalGroupTrack, VerticalGroup.id == VerticalGroupTrack.vertical_group_id
        )
        .filter(VerticalGroupTrack.track_name == bindparam("track_name"))
    )

    vertical_groups = query(db.session()).params(track_name=track_name).all()
    return vertical_groups
