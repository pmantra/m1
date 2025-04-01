"""
backfill_virtual_event_categories.py

Associate existing virtual events with virtual event category records
using their free text `category` field.  If no match exists, associate
virtual event with an "other" category.

Usage:
    backfill_virtual_event_categories.py [--force]

Options:
  --force                       Actually commit the changes
"""
from docopt import docopt

from app import create_app
from models.virtual_events import VirtualEvent, VirtualEventCategory
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_virtual_event_categories(force=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Ann L estimates there are about 180-200 events in the prod db; we should be okay
    events = VirtualEvent.query.all()

    other_category = VirtualEventCategory.query.filter_by(name="other").one_or_none()
    had_category_count = 0
    added_matching_category_count = 0
    added_other_category_count = 0

    for event in events:
        if event.virtual_event_category:
            had_category_count += 1
        else:
            matching_category = VirtualEventCategory.query.filter_by(
                name=event.category
            ).one_or_none()
            if matching_category:
                event.virtual_event_category = matching_category
                db.session.add(event)
                added_matching_category_count += 1
            else:
                if not other_category:
                    other_category = VirtualEventCategory(name="other")
                log.warn("Adding 'other' category to virtual event", id=event.id)
                event.virtual_event_category = other_category
                db.session.add(event)
                added_other_category_count += 1

    log.info(f"Added matching categories to {added_matching_category_count} events.")
    log.info(f"Added 'other' category to {added_other_category_count} events.")
    log.info(f"{had_category_count} events already had categories.")

    if force:
        db.session.commit()
    else:
        log.info("...but rolling back.")
        db.session.rollback()


if __name__ == "__main__":
    args = docopt(__doc__)
    with create_app().app_context():
        backfill_virtual_event_categories(force=args["--force"])
