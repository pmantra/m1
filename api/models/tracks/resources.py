from typing import TYPE_CHECKING, Sequence

from sqlalchemy import and_, bindparam
from sqlalchemy.ext import baked

from models.marketing import (
    Resource,
    ResourceConnectedContentTrackPhase,
    ResourceTrack,
    ResourceTrackPhase,
)
from storage.connection import db

if TYPE_CHECKING:
    from models.tracks import TrackName

bakery = baked.bakery()  # type: ignore[call-arg,func-returns-value] # Missing positional argument "initial_fn" in call to "__call__" of "Bakery" #type: ignore[func-returns-value] # Function does not return a value (it only ever returns None)


def resources_for_track_query() -> baked.BakedQuery:
    query: baked.BakedQuery = bakery(
        lambda session: session.query(Resource)
        .join(ResourceTrack, Resource.id == ResourceTrack.resource_id)
        .filter(ResourceTrack.track_name == bindparam("track_name"))
    )
    return query


def get_resources_for_track(track_name: "TrackName") -> Sequence[Resource]:
    query = resources_for_track_query()
    resources = query(db.session()).params(track_name=track_name).all()
    return resources


def resources_for_track_phase_query() -> baked.BakedQuery:
    query: baked.BakedQuery = bakery(
        lambda session: session.query(Resource)
        .join(ResourceTrackPhase, Resource.id == ResourceTrackPhase.resource_id)
        .filter(
            and_(
                ResourceTrackPhase.track_name == bindparam("track_name"),
                ResourceTrackPhase.phase_name == bindparam("phase_name"),
            )
        )
    )

    return query


def get_resources_for_track_phase(
    track_name: "TrackName", phase_name: str
) -> Sequence[Resource]:
    query = resources_for_track_phase_query()
    resources = (
        query(db.session()).params(track_name=track_name, phase_name=phase_name).all()
    )
    return resources


def connected_content_for_track_phases_query() -> baked.BakedQuery:
    query: baked.BakedQuery = bakery(
        lambda session: session.query(Resource)
        .join(
            ResourceConnectedContentTrackPhase,
            Resource.id == ResourceConnectedContentTrackPhase.resource_id,
        )
        .filter(
            and_(
                ResourceConnectedContentTrackPhase.track_name
                == bindparam("track_name"),
                ResourceConnectedContentTrackPhase.phase_name
                == bindparam("phase_name"),
            )
        )
    )
    return query


def get_connected_content_for_track_phases(
    track_name: "TrackName", phase_name: str
) -> Sequence[Resource]:
    query = connected_content_for_track_phases_query()
    resources = (
        query(db.session()).params(track_name=track_name, phase_name=phase_name).all()
    )
    return resources


def add_connected_content_to_track_phase(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    track_name: "TrackName", phase_name: str, *resource_ids
):
    with db.session.begin_nested():
        db.session.bulk_insert_mappings(
            ResourceConnectedContentTrackPhase,
            [
                {"resource_id": rid, "track_name": track_name, "phase_name": phase_name}
                for rid in resource_ids
            ],
        )
