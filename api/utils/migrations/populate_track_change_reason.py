from models.tracks.member_track import TrackChangeReason
from storage.connection import db
from utils.log import logger

log = logger(__name__)


track_change_reasons_list = [
    (1, "bug", "Bug", "Ex: member cannot self-transition in product due to bug"),
    (2, "care_team_error", "Care team error", None),
    (
        3,
        "organizational_change",
        "Organizational change",
        "Ex: organization acquired or breaks off",
    ),
    (
        4,
        "system_error",
        "System error",
        "Ex: organization_employee_id assigned to a member in the wrong organization",
    ),
    (
        5,
        "system_limitation",
        "System limitation",
        "Ex: transitions not available in the product",
    ),
    (6, "user_error", "User error", "Ex: wrong track selected or wrong account"),
    (7, "user_request", "User request", "Ex: members do not want to self-transition"),
]


def populate_track_change_reason_table():  # type: ignore[no-untyped-def] # Function is missing a return type annotation

    for (id, n, dn, desc) in track_change_reasons_list:
        tcr = TrackChangeReason(id=id, name=n, display_name=dn, description=desc)
        db.session.add(tcr)
        log.info("Added TrackChangeReason", track_change_reason=tcr.name)

    db.session.commit()
