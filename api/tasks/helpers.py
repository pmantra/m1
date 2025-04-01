from __future__ import annotations

import ddtrace
from sqlalchemy.orm.exc import NoResultFound

from appointments.models.appointment import Appointment
from authn.models.user import User
from storage.connection import db
from utils.log import logger

log = logger(__name__)


@ddtrace.tracer.wrap()
def get_user(user_id: int | str) -> User | None:
    try:
        user = db.session.query(User).filter(User.id == int(user_id)).one()
    except NoResultFound:
        log.info("User does not exist!", user_id=user_id)
    except ValueError:
        log.info("Bad value in user_id for get_user.", user_id=user_id)
    else:
        return user
    return None


@ddtrace.tracer.wrap()
def get_appointment(appointment_id: int | str) -> Appointment | None:
    try:
        appointment = (
            db.session.query(Appointment)
            .filter(Appointment.id == int(appointment_id))
            .one()
        )
    except NoResultFound:
        log.info("Appointment does not exist!", appointment_id=appointment_id)
    except ValueError:
        log.info(
            "Bad value in appointment_id for get_appointment.",
            appointment_id=appointment_id,
        )
    else:
        return appointment
    return None
