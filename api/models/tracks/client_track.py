from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional

from flask_babel import force_locale
from maven import feature_flags
from pymysql import Connection
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    bindparam,
    event,
    inspect,
)
from sqlalchemy.ext import baked
from sqlalchemy.orm import Mapper, relationship, validates

from models.base import TimeLoggedModelBase
from storage.connection import db
from utils.log import logger

from .track import TrackConfig, TrackName, get_track, validate_name

bakery = baked.bakery()  # type: ignore[call-arg,func-returns-value] # Missing positional argument "initial_fn" in call to "__call__" of "Bakery" #type: ignore[func-returns-value] # Function does not return a value (it only ever returns None)
log = logger(__name__)
DOULA_ONLY_TRACK_RELEASE_FLAG = "enable-doula-only-track"

TRACK_MODIFIERS_ENABLED_TRACKS = [
    TrackName.PREGNANCY,
    TrackName.POSTPARTUM,
    TrackName.PARTNER_PREGNANT,
    TrackName.PARTNER_NEWPARENT,
    TrackName.PREGNANCYLOSS,
    TrackName.PREGNANCY_OPTIONS,
]


def should_enable_doula_only_track() -> bool:
    return feature_flags.bool_variation(
        DOULA_ONLY_TRACK_RELEASE_FLAG,
        default=False,
    )


class TrackModifiers(str, enum.Enum):
    DOULA_ONLY = "doula_only"


class ClientTrack(TimeLoggedModelBase):
    __tablename__ = "client_track"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "track",
            "length_in_days",
            "active",
            name="uc_client_track_organization_track",
        ),
    )

    id = Column(Integer, primary_key=True)
    track = Column(String(120), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    organization = relationship("Organization", back_populates="client_tracks")
    # Whether this is a current/upcoming track. Set to False to mark as "deactivated."
    # To create a ClientTrack now that goes live later, set active=True and set a future launch_date.
    active = Column(Boolean, default=True, nullable=False)
    # Date to "launch" this track to members who are employees of this organization
    launch_date = Column(Date(), nullable=True)
    member_tracks = relationship("MemberTrack", back_populates="client_track")
    length_in_days = Column(Integer, nullable=True)
    ended_at = Column(Date(), nullable=True)
    track_modifiers = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ClientTrack[{self.id}] {self.organization.name} {self.track}>"

    __str__ = __repr__

    @classmethod
    def exists_query(cls) -> baked.BakedQuery:
        q = bakery(
            lambda session: session.query(
                session.query(cls)
                .filter(
                    (cls.track == bindparam("track"))
                    & (cls.organization_id == bindparam("org_id"))
                )
                .exists()
            )
        )
        return q

    @classmethod
    def exists(cls, track: TrackName, org_id: int) -> bool:
        query = cls.exists_query()
        return query(db.session()).params(track=track, org_id=org_id).scalar()

    @validates("track")
    def validate_track(self, key, track):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        validate_name(self, key, track)
        return track

    @validates("track_modifiers")
    def validate_track_modifiers(self, key: Any, value: str) -> str:
        if value and self.name not in TRACK_MODIFIERS_ENABLED_TRACKS:
            raise ValueError(
                f"Cannot apply track modifiers to invalid track {self.name}"
            )
        return value

    @property
    def is_maternity(self) -> bool:
        return self._config.is_maternity  # type: ignore[return-value] # Incompatible return value type (got "Optional[bool]", expected "bool")

    @property
    def is_available_to_members(self) -> bool:
        return (
            self.active
            and (not self.launch_date or self.launch_date <= date.today())
            and not self.ended_at
        )

    @property
    def name(self) -> TrackName:
        return TrackName(self.track)

    @property
    def display_name(self) -> Optional[str]:
        return self._config.display_name

    @property
    def _config(self) -> TrackConfig:
        return get_track(self.track)

    @property
    def length(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return timedelta(days=self.length_in_days)  # type: ignore[arg-type] # Argument "days" to "timedelta" has incompatible type "Optional[int]"; expected "float"

    @property
    def is_extended(self) -> bool:
        """
        This concept is a bit outdated, but we need to keep this property around for
        backwards compatibility. The logic is now: is this client track configured to be
        the longest it can be? If so, it's "extended". Otherwise, it's not.
        """
        length_in_days_options = self._config.length_in_days_options
        has_extension = len(length_in_days_options) > 1
        is_longest = self.length_in_days == max(length_in_days_options.values())
        return has_extension and is_longest

    @property
    def track_modifiers_list(self) -> list[TrackModifiers]:
        """
        Return list of modifiable attributes specific to the track
        :return:
        """

        if self.track_modifiers and should_enable_doula_only_track():
            # split the string and map it to the TrackModifiers enum
            try:
                track_modifiers_list = [
                    TrackModifiers(modifier)
                    for modifier in self.track_modifiers.split(",")
                ]
                return track_modifiers_list
            except ValueError as e:
                # handle invalid values that can't be converted to the enum
                raise ValueError(f"Invalid modifier in track_modifiers: {e}")
        return []


@event.listens_for(ClientTrack, "after_insert")
def update_zendesk_org_on_client_track_creation(
    mapper: Mapper, connection: Connection, target: ClientTrack
) -> None:
    # circular import
    from messaging.services.zendesk import update_zendesk_org

    # update the ZD org
    org_name = (
        target.organization.display_name
        if target.organization.display_name
        else target.organization.name
    )
    with force_locale("en"):
        update_zendesk_org.delay(
            target.organization.id,
            org_name,
            [
                ZendeskClientTrack.build_from_client_track(track)
                for track in target.organization.client_tracks
            ],
            target.organization.US_restricted,
            target.name,
        )


@event.listens_for(ClientTrack, "after_update")
def update_zendesk_org_on_client_track_update(
    mapper: Mapper, connection: Connection, target: ClientTrack
) -> None:
    # circular import
    from messaging.services.zendesk import update_zendesk_org

    active_history = inspect(target).get_history("active", True)
    if active_history.has_changes():
        # update the ZD org
        org_name = (
            target.organization.display_name
            if target.organization.display_name
            else target.organization.name
        )
        with force_locale("en"):
            update_zendesk_org.delay(
                target.organization.id,
                org_name,
                [
                    ZendeskClientTrack.build_from_client_track(track)
                    for track in target.organization.client_tracks
                ],
                target.organization.US_restricted,
                target.name,
            )


@dataclass
class ZendeskClientTrack:
    active: bool
    name: str
    display_name: str | None

    @staticmethod
    def build_from_client_track(client_track: ClientTrack) -> ZendeskClientTrack:
        return ZendeskClientTrack(
            active=client_track.active,
            name=client_track.name,
            display_name=client_track.display_name,
        )
