"""
seed_virtual_event_categories.py

Create VirtualEventCategory and VirtualEventCategoryTrack records
based on a currently hardcoded list of supported categories

Usage:
    seed_virtual_event_categories.py [--force]

Options:
  --force                       Actually commit the changes
"""
from docopt import docopt

from app import create_app
from models.virtual_events import (  # type: ignore[attr-defined] # Module "models.virtual_events" has no attribute "EVENT_CATEGORY_TRACK_WEEK_MAP"
    EVENT_CATEGORY_TRACK_WEEK_MAP,
    VirtualEventCategory,
    VirtualEventCategoryTrack,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def seed_categories_and_tracks(force=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    categories = []
    for category, availability_list in EVENT_CATEGORY_TRACK_WEEK_MAP.items():
        try:
            log.info(f"Adding VirtualEventCategory {category.value}")
            category = VirtualEventCategory(name=category.value)
            categories.append(category)
            db.session.add(category)

            for availability in availability_list:
                category_track = VirtualEventCategoryTrack(
                    # We are not including the hardcoded start week and end week because
                    # content/product have decided they don't want to restrict events
                    # by week at the moment.
                    category=category,
                    track_name=availability.track,
                )
                db.session.add(category_track)
        except Exception as e:
            log.error("Encountered error creating virtual event categories", error=e)
            db.session.rollback()
            return

    if force:
        db.session.commit()
    else:
        log.info("...but rolling back.")
        db.session.rollback()


if __name__ == "__main__":
    args = docopt(__doc__)
    with create_app().app_context():
        seed_categories_and_tracks(force=args["--force"])
