from sqlalchemy import and_, func, literal

from models.enterprise import (
    Organization,
    OrganizationModuleExtension,
    organization_approved_modules,
)
from models.programs import Module
from models.tracks.client_track import (  # type: ignore[attr-defined] # Module "models.tracks.client_track" has no attribute "TrackExtension"
    ClientTrack,
    TrackExtension,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_and_export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    backfill_client_tracks_and_extensions()


def backfill_client_tracks_and_extensions():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log_ = log.bind()
    log_.info("Starting backfill for ClientTracks and TrackExtensions.")
    updates, inserts = _get_client_track_mappings()
    if updates:
        log_.info("Updating existing ClientTracks.", updates=len(updates))
        db.session.bulk_update_mappings(ClientTrack, updates)
    if inserts:
        log_.info("Inserting new ClientTracks.", client_track_inserts=len(inserts))
        db.session.bulk_insert_mappings(ClientTrack, inserts)
    db.session.commit()
    log_.info("Done.")


def _get_client_tracks():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    query = (
        db.session.query(
            ClientTrack.id,
            ClientTrack.extension_id,
            Organization.id.label("organization_id"),
            Module.name.label("track"),
            func.lower(OrganizationModuleExtension.extension_logic).label(
                "extension_logic"
            ),
            OrganizationModuleExtension.extension_days,
            literal(True).label("active"),
        )
        .select_from(organization_approved_modules)
        .join(Organization, Module)
        .outerjoin(
            OrganizationModuleExtension,
            and_(
                OrganizationModuleExtension.organization_id == Organization.id,
                OrganizationModuleExtension.module_id == Module.id,
            ),
        )
        .outerjoin(
            ClientTrack,
            and_(
                ClientTrack.organization_id == Organization.id,
                ClientTrack.track == Module.name,
            ),
        )
    )
    return query.all()


def _get_existing_track_extensions():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    query = db.session.query(
        TrackExtension.id, TrackExtension.extension_logic, TrackExtension.extension_days
    )
    return query.all()


def _get_client_track_mappings(log_=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log_ = log_ or log.bind()
    client_tracks = _get_client_tracks()
    extensions_by_key = {
        (e.extension_logic, e.extension_days): e
        for e in _get_existing_track_extensions()
    }
    log_.info(
        "Got all ClientTracks and TrackExtensions.",
        client_tracks=len(client_tracks),
        extensions=len(extensions_by_key),
    )
    new_extensions = {
        (ct.extension_logic, ct.extension_days)
        for ct in client_tracks
        if (ct.extension_logic, ct.extension_days) != (None, None)
        and (ct.extension_logic, ct.extension_days) not in extensions_by_key
    }
    if new_extensions:
        log_.debug("Found new extensions.", new_extensions=len(new_extensions))
        db.session.bulk_insert_mappings(
            TrackExtension,
            [
                {"extension_logic": logic, "extension_days": days}
                for logic, days in new_extensions
            ],
        )
        extensions_by_key = {
            (e.extension_logic, e.extension_days): e
            for e in _get_existing_track_extensions()
        }
        log_.debug(
            "Created new extensions and re-fetched all extensions.",
            extensions=len(extensions_by_key),
        )
    client_track_updates = []
    client_track_inserts = []
    for ct in client_tracks:
        mapping: dict = ct._asdict()
        ext = extensions_by_key.get((ct.extension_logic, ct.extension_days))
        ext_id = ext and ext.id
        if ext_id != ct.extension_id:
            mapping["extension_id"] = ext_id
        else:
            # Don't need this index
            mapping.pop("extension_id")
        if ct.id:
            # Don't need these indexes
            mapping.pop("organization_id")
            mapping.pop("track")
            client_track_updates.append(mapping)
        else:
            mapping.pop("id")
            client_track_inserts.append(mapping)
    return client_track_updates, client_track_inserts
