import time

from app import create_app
from models.enterprise import Organization
from models.tracks import ClientTrack
from storage.connection import db
from utils.log import logger
from utils.query import paginate

log = logger(__name__)


def populate_client_track_in_orgs():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    start_time = time.time()
    size = 1000
    mappings = []
    idx = 0

    orgs = (
        db.session.query(Organization)
        .join(Organization.client_tracks)
        .filter(ClientTrack.track.in_(["general_wellness", "pregnancy"]))
    )
    print(f"updating client tracks for {orgs.count()} orgs")
    for org in paginate(orgs, Organization.id, size=size):
        if "pregnancy_options" in [track.track for track in org.client_tracks]:
            continue
        mapping = dict(
            track="pregnancy_options",
            organization=org,
            organization_id=org.id,
            extension_id=None,
            active=True,
            launch_date=None,
            length_in_days=364,
        )
        print(f"mapping {mapping}, org: {org.id}")
        mappings.append(mapping)
        idx += 1
        if idx % size == 0:
            log.info(f"Committing chunk size: {idx}")
            db.session.bulk_insert_mappings(ClientTrack, mappings)
            db.session.commit()
            mappings.clear()

    remainder = len(mappings)
    log.info(f"Committing remaining {remainder} bulk mappings.")
    db.session.bulk_insert_mappings(ClientTrack, mappings)
    db.session.commit()
    mappings.clear()

    elapsed = time.time() - start_time
    log.info(f"Total execution time in seconds: {elapsed}")


if __name__ == "__main__":
    print("Adding client_tracks to orgs")
    with create_app().app_context():
        populate_client_track_in_orgs()
