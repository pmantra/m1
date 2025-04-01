from sqlalchemy.orm import joinedload

from models.tracks import ClientTrack, get_track
from storage.connection import db


def run(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    client_tracks = (
        db.session.query(ClientTrack).options(joinedload(ClientTrack.extension)).all()
    )

    # Find lengths for each client track
    for client_track in client_tracks:
        default_days = get_track(client_track.track).length.days
        ext = client_track.extension
        extension_days = ext.extension_days if ext else 0
        length = default_days + extension_days
        client_track.length_in_days = length

    if dry_run:
        print("Dry run, rolling back.")
        db.session.rollback()
    else:
        print("Committing changes...")
        db.session.commit()
