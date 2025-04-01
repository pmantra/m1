from __future__ import annotations

import dataclasses
import enum
import functools
import json
import pathlib
from copy import deepcopy
from datetime import timedelta
from typing import Dict, Iterable, Mapping, Optional, Sequence

from flask_babel import LazyString, lazy_gettext
from marshmallow import ValidationError

__all__ = (
    "configured_tracks",
    "get_track",
    "validate_names",
    "OnboardingConfig",
    "partner_track_mappings",
    "RequiredInformation",
    "TrackConfig",
    "TrackName",
    "TransitionConfig",
    "validate_name",
    "get_renewable_tracks",
)
TRACK_JSON_LOCALIZATION_ENABLED = "release-track-json-localization"

ROOT_DIR = pathlib.Path(__file__).parent.absolute()
CONFIG_DIR = ROOT_DIR / "configuration"
TRACK_CONFIG_L10N = CONFIG_DIR / "track_l10n.json"


@functools.lru_cache(maxsize=1)
def _load_track_configuration_l10n():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if not TRACK_CONFIG_L10N.exists():
        raise RuntimeError(
            f"No track configuration provided @ {str(TRACK_CONFIG_L10N)!r}."
        )

    return json.loads(TRACK_CONFIG_L10N.read_bytes())


@functools.lru_cache(maxsize=1)
def _configured_tracks_l10n() -> Mapping[str, "TrackConfig"]:
    return {
        TrackName(n): TrackConfig.from_config(c, localized=True)
        for n, c in _load_track_configuration_l10n().items()
    }


def configured_tracks() -> Mapping[str, "TrackConfig"]:
    return _configured_tracks_l10n()


def get_track(name: str) -> "TrackConfig":
    config = configured_tracks()
    if name not in config:
        raise RuntimeError(f"Track {name!r} is not configured!")
    return config[name]


@functools.lru_cache(maxsize=1)
def partner_track_mappings() -> Mapping[str, str]:
    return {
        t.name: t.partner_track for t in configured_tracks().values() if t.partner_track
    }


@functools.lru_cache(maxsize=2000)
def validate_name(instance, key: str, name: Optional[str]) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    tracks = configured_tracks().keys()
    valid = name is None or name in tracks
    if not valid:
        raise ValueError(
            f"{instance.__class__.__name__}.{key}: "
            f"{name} is not a configured Track in {str(TRACK_CONFIG_L10N)!r}."
        )
    return valid


def validate_names(names: list[str]) -> bool:
    tracks = configured_tracks().keys()
    for n in names:
        if n not in tracks:
            raise ValidationError(
                f"{n} is not a configured Track in {str(TRACK_CONFIG_L10N)!r}."
            )
    return True


def get_renewable_tracks() -> list[str]:
    return [t.name for t in configured_tracks().values() if t.can_be_renewed]


@dataclasses.dataclass(frozen=True)
class TrackConfig:
    """A static object representing the essential fields for configuring a MemberTrack.

    Notes:
        Should not be initialized directly - this is a direct representation of the
        track data in `configuration/track_l10.json`.

        The public factory `Track.from_name()` should be used.

    Examples:
        >>> postpartum_config = TrackConfig.from_name(TrackName.POSTPARTUM)
    """

    name: "TrackName"
    """The enumerated name of the configured track."""
    display_name: Optional[str | LazyString]
    """The display name for a track used on frontends."""
    onboarding: "OnboardingConfig"
    """Configuration related to how this track is displayed during onboarding."""
    is_maternity: Optional[bool]
    """Whether the track is available only to members or beneficiaries who can get pregnant"""
    length: timedelta
    """Configuration related to how long this track should last, in weeks."""
    length_in_days_options: Dict[str, int]
    """Options for how long this track should last, by name. If there is more than one,
    admins can choose how long each client track should be."""
    display_length: Optional[str | LazyString]
    """The length of a track as displayed on frontends."""
    length_in_days: Optional[int]
    "Length of a track in days."
    grace_period: timedelta
    """The length of the grace period. The JSON key is 'grace_period_days' (# of days)

    During the grace period, the user is moved into the end phase of their current track.
    After their grace period has ended, the user's member track is terminated.
    For pregnancy, grace period is 0, but a buffer is set on the track implementation itself
    to avoid situations where we transition the user to postpartum too early."""
    intro_message: Optional[str | LazyString]
    """The default first message sent to a user from their Care Advocate."""
    required_information: Iterable["RequiredInformation"]
    """Required fields for the track.

    The only currently supported values are 'DUE_DATE' and 'CHILD_BIRTH'.
    """
    transitions: Sequence["TransitionConfig"]
    """The list of tracks that this track can transition to."""
    phase_type: "PhaseType"
    """The phase type for the track. The supported values are 'static' and 'weekly.'

    Used to generate phase names. Actual behavior is determined by the MemberTrack subclass.
    """

    image: str
    """The full URL of an image to display for this track in onboarding/programs UIs"""
    description: str | LazyString
    """A description of the track, for the onboarding/my programs UI"""

    priority: int
    """A score between 0 and 100 to indicate track priority compared to other tracks.
    If a member has more than one active tracks, the track with highest priority will be
    taken into for CA assignment
    Tracks with priority 100 are eligible for CA intro appointments.
    """
    enrollment_requirement_description: Optional[str]
    """A short description of the requirements to enroll in the track, for the UI"""
    life_stage: Optional[str]
    """The life stage this track falls under.

    The supported values are 'starting', 'raising', and 'planning'.
    """
    track_selection_category: Optional[str]
    """The track selection category this track falls under. This is a replacement for
    life_stage on the new track selection page
   
    The supported values are 'pregnancy_postpartum', 'family_planning', and 'parenting_wellness'
    """
    auto_transition_to: Optional["TrackName"] = None
    """The track which this track will transition to after reaching the scheduled end."""
    partner_track: Optional["TrackName"] = None
    """Which track is considered a 'partner' to this one."""
    restrict_booking_verticals: bool = False
    """Whether the verticals we search with on booking should be restricted.

    If `True`, only vertical groups associated to this track will be available,
    otherwise, all vertical groups are valid.
    """
    can_be_renewed: bool = False
    """Whether the track is a type that can be renewed"""

    descriptions_by_length_in_days: Optional[Dict[str, str | LazyString]] = None
    """Additional track descriptions for non-default track lengths"""

    track_unavailable_for_transition_message: Optional[str | LazyString] = None
    """A message to show members if the given track is not available to transition to"""

    deprecated: bool = False
    """Whether the track is deprecated and should not be used for new enrollments"""

    localized: bool = False

    @classmethod
    def from_config(cls, track_config: Dict, localized: bool = False) -> "TrackConfig":
        track_config = deepcopy(track_config)
        onboarding_config: dict = track_config.pop("onboarding")
        required_information_config: list = track_config.pop("required_information", [])
        transitions_config = track_config.pop("transitions", [])
        auto_transition_to = track_config.pop("auto_transition_to", None)
        length_in_days = track_config.pop("length_in_days", None)
        return cls(
            name=TrackName(track_config.pop("name")),
            onboarding=OnboardingConfig(**onboarding_config),
            required_information=[
                RequiredInformation(field) for field in required_information_config
            ],
            length=timedelta(weeks=track_config.pop("length")),
            grace_period=timedelta(days=track_config.pop("grace_period_days", 0)),
            transitions=[
                TransitionConfig(**transition) for transition in transitions_config
            ],
            auto_transition_to=auto_transition_to and TrackName(auto_transition_to),
            phase_type=PhaseType(track_config.pop("phase_type")),
            length_in_days=length_in_days,
            localized=localized,
            **track_config,
        )

    def __post_init__(self) -> None:
        if self.localized:
            if self.display_name:
                object.__setattr__(
                    self, "display_name", lazy_gettext(self.display_name)
                )

            if self.display_length:
                object.__setattr__(
                    self, "display_length", lazy_gettext(self.display_length)
                )

            if self.intro_message:
                object.__setattr__(
                    self, "intro_message", lazy_gettext(self.intro_message)
                )

            if self.description:
                object.__setattr__(self, "description", lazy_gettext(self.description))

            if self.track_unavailable_for_transition_message:
                object.__setattr__(
                    self,
                    "track_unavailable_for_transition_message",
                    lazy_gettext(self.track_unavailable_for_transition_message),
                )

            if self.onboarding:
                translated_onboarding = OnboardingConfig(
                    label=lazy_gettext(self.onboarding.label),
                    order=self.onboarding.order,
                    as_partner=self.onboarding.as_partner,
                )
                object.__setattr__(self, "onboarding", translated_onboarding)

            if self.transitions:
                translated_transitions = [
                    TransitionConfig(
                        name=transition.name,
                        display_description=lazy_gettext(
                            transition.display_description
                        ),
                    )
                    for transition in self.transitions
                ]
                object.__setattr__(self, "transitions", translated_transitions)

            if self.descriptions_by_length_in_days:
                translated_descriptions_by_length_in_days = {
                    key: lazy_gettext(value)
                    for key, value in self.descriptions_by_length_in_days.items()
                }
                object.__setattr__(
                    self,
                    "descriptions_by_length_in_days",
                    translated_descriptions_by_length_in_days,
                )

    @classmethod
    def from_name(cls, name: "TrackName"):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Fetch a track configuration from its unique name.

        Args:
            name: The unique name of the track.

        Raises:
            RuntimeError: If a track name is provided with no mapped configuration

        Returns:
            The static TrackConfig for the associated name.
        """
        return get_track(name)


@dataclasses.dataclass(frozen=True)
class TransitionConfig:
    __slots__ = ("name", "display_description")

    name: "TrackName"
    """The Track name that the transition will lead to."""
    display_description: str | LazyString
    """The frontend label for this Transition."""


@dataclasses.dataclass(frozen=True)
class OnboardingConfig:
    """Essential fields for displaying a Track during onboarding."""

    label: Optional[str | LazyString]
    """The frontend label for this Track."""
    order: Optional[int]
    """The order in which this Track is displayed during selection."""
    as_partner: bool = False
    """Which to display this Track as a 'partner track'."""


class RequiredInformation(str, enum.Enum):
    CHILD_BIRTH = "CHILD_BIRTH"
    DUE_DATE = "DUE_DATE"

    @classmethod
    def _missing_(cls, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        uppercased = value.upper()
        if uppercased in RequiredInformation.__members__:
            return cls(uppercased)
        raise ValueError(f"Unrecognized required_information field: {value}")


class TrackName(str, enum.Enum):
    ADOPTION = "adoption"
    BREAST_MILK_SHIPPING = "breast_milk_shipping"
    EGG_FREEZING = "egg_freezing"
    FERTILITY = "fertility"
    GENERAL_WELLNESS = "general_wellness"
    GENERIC = "generic"
    PARENTING_AND_PEDIATRICS = "parenting_and_pediatrics"
    PARTNER_FERTILITY = "partner_fertility"
    PARTNER_NEWPARENT = "partner_newparent"
    PARTNER_PREGNANT = "partner_pregnant"
    POSTPARTUM = "postpartum"
    PREGNANCY = "pregnancy"
    PREGNANCYLOSS = "pregnancyloss"
    PREGNANCY_OPTIONS = "pregnancy_options"
    SPONSORED = "sponsored"
    SURROGACY = "surrogacy"
    TRYING_TO_CONCEIVE = "trying_to_conceive"
    MENOPAUSE = "menopause"

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def isvalid(cls, value: str) -> bool:
        try:
            TrackName(value)
            return True
        except ValueError:
            return False


class PhaseType(str, enum.Enum):
    STATIC = "static"
    WEEKLY = "weekly"
