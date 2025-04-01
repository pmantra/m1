from datetime import datetime

from sqlalchemy.orm import joinedload

from authn.models.user import User
from models.profiles import CareTeamTypes
from models.profiles import MemberPractitionerAssociation as MPA
from models.tracks import MemberTrack, TrackName
from storage.connection import db
from utils.log import logger

_log = logger(__name__)
mapping = {48023: 146189, 56: 167335, 209057: 213561}
incorrect_ids = set(mapping.keys())
correct_ids = set(mapping.values())


def repair_fertility_care_teams(force=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation

    log = _log.bind(mode="[LIVE RUN]" if force else "[DRY RUN]")

    affected_users = (
        User.query.join(User.practitioner_associations)
        .options(joinedload(User.practitioner_associations))
        .join(MemberTrack)
        .filter(
            MemberTrack.active,
            MemberTrack.name == TrackName.FERTILITY.value,
            MPA.type == CareTeamTypes.QUIZ,
            MPA.practitioner_id.in_(list(incorrect_ids)),
            MPA.created_at >= datetime(2021, 1, 5, 16, 40),
        )
        .all()
    )

    log.info(
        "Fixing care teams for users affected by fertility misconfiguration.",
        affected_user_count=len(affected_users),
    )

    for u in affected_users:
        log.info("Repairing fertility care team.", user_id=u.id)
        correct_id_missing = True
        incorrect_id = None
        for mpa in u.practitioner_associations:
            if mpa.practitioner_id in correct_ids:
                log.info(
                    "User already has a repaired fertility care team.",
                    user_id=u.id,
                    mpa_id=mpa.id,
                )
                correct_id_missing = False
            elif (
                mpa.type == CareTeamTypes.QUIZ and mpa.practitioner_id in incorrect_ids
            ):
                log.info(
                    "Removing incorrect fertility care team practitioner.",
                    mpa_id=mpa.id,
                    user_id=mpa.user_id,
                    practitioner_id=mpa.practitioner_id,
                    type=mpa.type,
                )
                incorrect_id = mpa.practitioner_id
                if force:
                    db.session.delete(mpa)
        db.session.expire(u, ["practitioner_associations"])
        if correct_id_missing:
            corrected_id = mapping[incorrect_id]  # type: ignore[index] # Invalid index type "Optional[Any]" for "Dict[int, int]"; expected type "int"
            u_fertility_track = next(
                t for t in u.active_tracks if t.name == TrackName.FERTILITY.value
            )
            log.info(
                "Adding corrected fertility care team practitioner.",
                user_id=u.id,
                track_id=u_fertility_track.id,
                incorrect_id=incorrect_id,
                corrected_id=corrected_id,
            )
            if force:
                u.add_track_onboarding_care_team_member(
                    corrected_id, member_track=u_fertility_track
                )
        if force:
            db.session.commit()
