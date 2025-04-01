"""
create_track_tags.py

Creates tag entries for each possible track. These can be used to tag entries with certain tracks for filtering or
sorting later.

Usage:
    create_track_tags.py
"""
import contentful_management

from app import create_app
from learn.utils.migrations import constants
from models.tracks import TrackName
from utils.log import logger

log = logger(__name__)

client = contentful_management.Client(constants.CONTENTFUL_MANAGEMENT_KEY)


def create_track_tags() -> None:
    tags_proxy = client.tags(
        constants.CONTENTFUL_SPACE_ID, constants.CONTENTFUL_ENVIRONMENT_ID
    )
    for track_name in TrackName:
        try:
            tags_proxy.find(track_name)
            log.info("Tag already exists for track.", track_name=str(track_name))
        except contentful_management.errors.NotFoundError:
            log.info(
                "Creating tag for track.",
                track_name=str(track_name),
            )
            tags_proxy.create(
                track_name, {"name": track_name, "sys": {"visibility": "public"}}
            )


if __name__ == "__main__":
    with create_app().app_context():
        create_track_tags()
