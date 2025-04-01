from __future__ import annotations

import datetime

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
from sqlalchemy.ext.baked import BakedQuery, Bakery
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from models import base
from models.base import db
from models.mixins import SVGImageMixin
from models.tracks import TrackName
from models.verticals_and_specialties import Specialty
from utils.data import JSONAlchemy

bakery: Bakery = BakedQuery.bakery()


DEFAULT_CATEGORY_IMAGE = "default-category-icon.svg"

need_need_category = base.db.Table(
    "need_need_category",
    Column("category_id", Integer, ForeignKey("need_category.id")),
    Column("need_id", Integer, ForeignKey("need.id")),
    UniqueConstraint("category_id", "need_id"),
)
need_specialty_keyword = base.db.Table(
    "need_specialty_keyword",
    Column("keyword_id", Integer, ForeignKey("specialty_keyword.id")),
    Column("need_id", Integer, ForeignKey("need.id")),
    UniqueConstraint("keyword_id", "need_id"),
)
need_specialty = base.db.Table(
    "need_specialty",
    Column("specialty_id", Integer, ForeignKey("specialty.id")),
    Column("need_id", Integer, ForeignKey("need.id")),
    UniqueConstraint("specialty_id", "need_id"),
)


class NeedTrack(base.ModelBase):
    __tablename__ = "tracks_need"

    track_name = Column(String, primary_key=True)
    need_id = Column(Integer, ForeignKey("need.id"), primary_key=True)

    need = relationship("Need")


class NeedAppointment(base.TimeLoggedModelBase):
    __tablename__ = "need_appointment"
    appointment_id = Column(
        Integer, ForeignKey("appointment.id"), primary_key=True, unique=True
    )
    need_id = Column(Integer, ForeignKey("need.id"), primary_key=True)


class NeedVertical(base.TimeLoggedModelBase):
    __tablename__ = "need_vertical"
    vertical_id = Column(Integer, ForeignKey("vertical.id"), primary_key=True)
    need_id = Column(Integer, ForeignKey("need.id"), primary_key=True)
    id = Column(Integer, autoincrement=True, unique=True, index=True)


class AllowedTracksMixin:
    @property
    def allowed_track_names(self) -> list[TrackName]:
        """
        Returns the names of the tracks for which this is the onboarding assessment lifecycle.
        """
        return [
            TrackName(t.track_name)
            for t in self.allowed_tracks  # type: ignore[attr-defined]
        ]


class Need(base.ModelBase, AllowedTracksMixin):
    __tablename__ = "need"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(70), nullable=False)
    description = Column(String(255))
    display_order = Column(Integer)
    slug = Column(String(128), unique=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.datetime.utcnow)

    categories = relationship(
        "NeedCategory", back_populates="needs", secondary=need_need_category
    )
    verticals = relationship("Vertical", secondary="need_vertical")
    keywords = relationship("SpecialtyKeyword", secondary=need_specialty_keyword)
    specialties = relationship("Specialty", secondary=need_specialty)

    allowed_tracks = relationship("NeedTrack", cascade="all, delete-orphan")

    need_verticals = relationship("NeedVertical")
    restricted_verticals = relationship(
        "NeedRestrictedVertical",
        secondary="need_vertical",
        back_populates="need",
        primaryjoin="Need.id==NeedVertical.need_id",
        secondaryjoin="NeedVertical.id==NeedRestrictedVertical.need_vertical_id",
    )
    promote_messaging = Column(Boolean, nullable=False, default=False)
    hide_from_multitrack = Column(Boolean, nullable=False, default=False)

    searchable_localized_data = Column(JSONAlchemy(Text), default={})

    @hybrid_property
    def non_restricted_verticals(self):
        from models.verticals_and_specialties import Vertical

        nrv_query = db.session.query(NeedRestrictedVertical.need_vertical_id)
        verticals = (
            db.session.query(Vertical)
            .join(NeedVertical)
            .filter(NeedVertical.need_id == self.id, NeedVertical.id.notin_(nrv_query))
            .all()
        )
        return verticals

    @non_restricted_verticals.setter  # type: ignore[no-redef]
    def non_restricted_verticals(self, non_restricted_verticals):
        verticals = set(self.verticals) - set(self.non_restricted_verticals)
        verticals.update(set(non_restricted_verticals))
        self.verticals = list(verticals)

    def get_restricted_verticals(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        need_vertical_ids = [nv.id for nv in self.need_verticals]
        result = (
            db.session.query(
                NeedRestrictedVertical,
                NeedVertical.vertical_id,
                NeedVertical.id,
                Specialty,
            )
            .join(
                NeedVertical, NeedRestrictedVertical.need_vertical_id == NeedVertical.id
            )
            .join(Specialty, NeedRestrictedVertical.specialty_id == Specialty.id)
            .filter(NeedVertical.id.in_(need_vertical_ids))
            .all()
        )

        restricted_verticals = {}
        for nrv in result:
            restricted_verticals.setdefault(nrv[1], {})
            restricted_verticals[nrv[1]].setdefault("vertical_id", nrv[1])
            restricted_verticals[nrv[1]].setdefault("need_vertical_id", nrv[2])
            restricted_verticals[nrv[1]].setdefault("specialties", [])
            restricted_verticals[nrv[1]]["specialties"].append(nrv[3])

        return restricted_verticals.values()

    def put_restricted_verticals(self, restricted_verticals):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        need_vertical_ids = [nv.id for nv in self.need_verticals]

        # Remove existing
        db.session.query(NeedRestrictedVertical).filter(
            NeedRestrictedVertical.need_vertical_id.in_(need_vertical_ids)
        ).delete(synchronize_session="fetch")

        # Add all
        db.session.bulk_save_objects(restricted_verticals)
        db.session.commit()

    def __repr__(self) -> str:
        return f"<Need[{self.id}: {self.name}]>"


class NeedCategory(base.ModelBase, SVGImageMixin, AllowedTracksMixin):
    __tablename__ = "need_category"

    id = Column(Integer, primary_key=True)
    name = Column(String(70), nullable=False)
    description = Column(String(255))
    parent_category_id = Column(Integer, ForeignKey("need_category.id"))
    parent_category = relationship("NeedCategory", remote_side=[id])
    display_order = Column(Integer)
    image_id = Column(String(70), nullable=True)
    needs = relationship(
        "Need", back_populates="categories", secondary="need_need_category"
    )
    slug = Column(String(128), unique=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.datetime.utcnow)
    hide_from_multitrack = Column(Boolean, nullable=False, default=False)

    allowed_tracks = relationship("NeedCategoryTrack", cascade="all, delete-orphan")

    searchable_localized_data = Column(JSONAlchemy(Text), default={})

    def __repr__(self) -> str:
        return f"<NeedCategory[{self.id}: {self.name} -  {self.allowed_tracks}]>"

    @property
    def image_id_or_default(self) -> str:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not self.image_id:
            return DEFAULT_CATEGORY_IMAGE
        return self.image_id

    __str__ = __repr__


class NeedCategoryTrack(base.ModelBase):
    __tablename__ = "tracks_need_category"

    track_name = Column(String, primary_key=True)
    need_category_id = Column(Integer, ForeignKey("need_category.id"), primary_key=True)

    need_category = relationship("NeedCategory")

    def __repr__(self) -> str:
        return f"{self.track_name}"


def get_needs_for_track(track_name: str) -> list[Need]:
    query: BakedQuery = bakery(
        lambda session: session.query(Need)
        .join(NeedTrack, Need.id == NeedTrack.need_id)
        .filter(NeedTrack.track_name == bindparam("track_name"))
    )  # type: ignore[func-returns-value]

    needs = query(db.session()).params(track_name=track_name).all()
    return needs


def get_need_categories_for_track(track_name: str) -> list[NeedCategory]:
    query: BakedQuery = bakery(
        lambda session: session.query(NeedCategory)
        .join(NeedCategoryTrack, NeedCategory.id == NeedCategoryTrack.need_category_id)
        .filter(NeedCategoryTrack.track_name == bindparam("track_name"))
    )  # type: ignore[func-returns-value]

    need_categories = query(db.session()).params(track_name=track_name).all()
    return need_categories


class NeedRestrictedVertical(base.TimeLoggedModelBase):
    __tablename__ = "need_restricted_vertical"

    need_vertical_id = Column(Integer, ForeignKey("need_vertical.id"), primary_key=True)
    need = relationship(
        "Need",
        secondary="need_vertical",
        back_populates="restricted_verticals",
        primaryjoin="NeedRestrictedVertical.need_vertical_id==NeedVertical.id",
        secondaryjoin="NeedVertical.need_id==Need.id",
    )
    specialty_id = Column(Integer, ForeignKey("specialty.id"), primary_key=True)

    @classmethod
    def create(cls, need_id, vertical_id, specialty_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        nv = (
            db.session.query(NeedVertical)
            .filter(
                NeedVertical.need_id == need_id,
                NeedVertical.vertical_id == vertical_id,
            )
            .one()
        )

        return cls(need_vertical_id=nv.id, specialty_id=specialty_id)

    def __repr__(self) -> str:
        return f"NeedRestrictedVertical[{self.need_vertical_id} - {self.specialty_id}]"

    __str__ = __repr__
