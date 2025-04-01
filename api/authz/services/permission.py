from __future__ import annotations

from typing import Iterable

from flask_principal import Need, Permission, RoleNeed
from flask_restful import abort

from appointments.models.appointment import Appointment
from authn.models.user import User
from authz.models.roles import ROLES, Role
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class RateLimitingException(Exception):
    pass


view_post = Permission(Need("get", "post"))
add_post = Permission(Need("post", "post"))
edit_post = Permission(Need("put", "post"))
delete_post = Permission(Need("delete", "post"))

add_schedule_event = Permission(Need("post", "schedule_event"))

add_appointment = Permission(Need("post", "appointment"))

member = Permission(RoleNeed(ROLES.member))


def only_member_or_practitioner(me: User, appointments: Iterable[Appointment]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    clean = []
    for appointment in appointments:
        if appointment.member_schedule_id == me.schedule.id:
            clean.append(appointment)
        elif me.practitioner_profile:
            if appointment.product.practitioner == me:
                clean.append(appointment)
        else:
            log.warning(
                "User was unable to access appointment",
                appointment_id=appointment.id,
                role=ROLES.member,
            )

    return clean


def only_mine(me, items):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def eval_item(item):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        owner_id = None

        if hasattr(item, "owner_id"):
            owner_id = item.owner_id
        elif hasattr(item, "author_id"):
            owner_id = item.author_id
        elif hasattr(item, "id"):
            owner_id = item.id

        if owner_id and owner_id == me.id:
            return item
        else:
            log.debug("%s not authorized for %s", me, item)
            abort(403, message="Not authorized!")

    if type(items) in (list, tuple):
        for item in items:
            eval_item(item)
    else:
        eval_item(items)

    return items


def only_specialists_and_me_or_only_me(me, users):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    practitioner = db.session.query(Role).filter(Role.name == ROLES.practitioner).one()

    if not practitioner or users is None:
        abort(403, message="Not authorized!")

    for user in users:
        user_id = user["id"]
        profile_names = set(user["profiles"])

        if me is not None and user_id == me.id:
            continue

        if practitioner.name not in profile_names:
            log.info("Not all practitioners!")
            abort(403, message="Not authorized!")

    return users


def add_role_to_user(user: User, role_name: str) -> None:
    role = Role.query.filter(Role.name == role_name).one_or_none()
    if role:
        user.roles = [role]
        db.session.add(user)
