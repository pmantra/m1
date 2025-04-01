from datetime import date, timedelta

from models.tracks import ChangeReason
from models.tracks.member_track import MemberTrack
from storage.connection import db
from utils.log import logger

log = logger(__name__)


# Sample usage:
# Update the anchor_date for a user with id 123 to today's date
# update_member_track_anchor_date(user_id=123, new_anchor_date=date.today(), dry_run=False)


def is_valid_date(date_to_check: date) -> bool:
    # Check if date is within 2 years from today
    today = date.today()
    two_years_later = today + timedelta(days=365 * 2)
    return date_to_check <= two_years_later


def update_member_track_anchor_date(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user_id: int, new_anchor_date: date, dry_run: bool = True
):
    if not is_valid_date(new_anchor_date):
        log.error("Invalid anchor date. Anchor date must be within 2 years from today.")
        return

    mt = db.session.query(MemberTrack).filter_by(user_id=user_id, active=True).first()
    if not mt:
        log.error(f"Active MemberTrack for user with id {user_id} does not exist.")
        return

    member_track_updates = [
        {
            "id": mt.id,
            "anchor_date": new_anchor_date,
            "change_reason": ChangeReason.MANUAL_UPDATE,
        }
    ]
    # Update anchor_date

    log.info("MemberTrack to be updated", member_track_updates=member_track_updates)

    if not dry_run:
        db.session.bulk_update_mappings(MemberTrack, member_track_updates)
        db.session.commit()
        log.info("MemberTrack updated successfully.")
    else:
        log.info("Dry run: MemberTrack not updated.")
