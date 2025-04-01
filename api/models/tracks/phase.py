import enum
import re
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.exc import ProgrammingError

from storage.connection import db

from .track import PhaseType, TrackName, get_track


@dataclass
class TrackAndPhaseName:
    __slots__ = ("track_name", "phase_name")
    track_name: TrackName
    phase_name: str

    def __repr__(self) -> str:
        return f"{self.track_name}/{self.phase_name}"

    __str__ = __repr__


class PhaseNamePrefix(str, enum.Enum):
    WEEKLY = "week"
    STATIC = "static"
    END = "end"


WEEKLY_PHASE_NAME_REGEX = re.compile(r"^week-(\d+)$")


class UnrecognizedPhaseName(Exception):
    pass


def convert_legacy_phase_name(phase_name: str, module_name: str) -> str:
    """
    This function is used in migrations during the Tracks rearchitecture.
    """

    if phase_name == module_name:
        return PhaseNamePrefix.STATIC.value
    elif phase_name.endswith("-end") or phase_name.endswith("transition"):
        return PhaseNamePrefix.END.value
    elif WEEKLY_PHASE_NAME_REGEX.match(phase_name):
        return phase_name

    raise UnrecognizedPhaseName(f"{phase_name!r} is not a recognized phase name format")


def ensure_new_phase_name(phase_name: str, module_name: str) -> str:
    """
    Returns the phase name as-is if it's valid in the new phase name schema,
    or converts it if it's a valid "legacy" phase name.

    Raises UnrecognizedPhaseName if phase name is not a valid legacy OR new phase name
    """

    # If the phase name is already in the new format, we don't need to do anything.
    if phase_name in (PhaseNamePrefix.STATIC, PhaseNamePrefix.END):
        return phase_name
    elif WEEKLY_PHASE_NAME_REGEX.match(phase_name):
        return phase_name

    # Assume it's a legacy phase name and try to convert it
    return convert_legacy_phase_name(phase_name, module_name)


def generate_phase_names(track_name: TrackName) -> Iterable[str]:
    """
    Returns a generator that yields the phase names for the given track.

    This is only intended for use in Admin, i.e. to populate phase select fields.
    To modify phase logic in the application runtime, see: ./member_track.py
    """
    from models.programs import Module, Phase

    track_config = get_track(track_name)
    if track_config.phase_type == PhaseType.WEEKLY:
        try:
            phases = (
                db.session.query(Phase)
                .join(Phase.module)
                .filter(Module.name == track_name)
                .all()
            )
        except ProgrammingError:
            # phase names cannot be loaded before the database has been initialized
            return
        week_num_phases = []
        other_phases = []
        for p in phases:
            if p.name.startswith("week-"):
                week_num_phases.append(p.name)
            else:
                other_phases.append(p.name)
        week_num_phases.sort(key=lambda x: int(x.split("week-")[1]))
        sorted_phase_names = week_num_phases + other_phases
        for phase_name in sorted_phase_names:
            yield phase_name

    else:
        yield "static"
    yield "end"
