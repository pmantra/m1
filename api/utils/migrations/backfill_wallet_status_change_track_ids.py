from sqlalchemy import or_

from authn.models.user import User
from models.programs import CareProgram
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def fix_track_id(action, force):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info("Fixing change_wallet_status action track id.", action_id=action.id)
    user = User.query.get(action.user_id)
    if not user:
        log.error(
            "Could not find user related to action.",
            user_id=action.user_id,
            action_id=action.id,
        )
        return
    pp = CareProgram.query.filter(
        CareProgram.user == user,
        CareProgram.created_at < action.created_at,
        or_(CareProgram.ended_at.is_(None), CareProgram.ended_at > action.created_at),
    ).all()
    if len(pp) != 1:
        log.error(
            "Expected exactly one active care program during action creation.",
            care_programs=", ".join(str(p.id) for p in pp),
        )
        return
    p = pp[0]
    if p.id == action.data.get("track_id"):
        log.info("Action had correct program id.")
        return
    log.info(
        "Found action care program id.",
        action_id=action.id,
        old_track_id=action.data.get("track_id"),
        care_program_id=p.id,
    )
    if force:
        action.data = {"track_id": p.id, **action.data}
        db.session.commit()
