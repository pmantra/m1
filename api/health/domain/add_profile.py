from __future__ import annotations

from datetime import date, datetime
from traceback import format_exc
from typing import Any, Optional

from sqlalchemy.orm.exc import NoResultFound

from authn.models.user import User
from authz.models.roles import ROLES, Role
from geography import CountryRepository
from health.models.health_profile import HealthProfile
from models.profiles import MemberProfile, PractitionerProfile, State
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def add_profile_to_user(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user: User, role_name=ROLES.member, state: str | None = None, **additional_inputs
) -> User:
    if not user.health_profile:
        hp = HealthProfile(user=user)
        db.session.add(hp)

    try:
        role = Role.query.filter(Role.name == role_name).one()
    except NoResultFound:
        log.warning("Role %s does not exist!", role_name)
        return user
    if role.name == ROLES.member and not user.member_profile:
        profile = MemberProfile()
        profile.role = role
        if profile.json is None:
            profile.json = {}
        # default to allow post session notes sharing
        profile.json["opted_in_notes_sharing"] = True
        if state is not None:
            profile.state = (
                db.session.query(State).filter(State.abbreviation == state).one()
            )
        add_name_information_to_profile(
            profile=profile,
            first_name=additional_inputs.get("first_name", None),
            last_name=additional_inputs.get("last_name", None),
            middle_name=additional_inputs.get("middle_name", None),
        )
        user.member_profile = profile
        db.session.add(profile)
    elif role.name == ROLES.practitioner and not user.practitioner_profile:
        profile = PractitionerProfile()
        profile.role = role
        add_name_information_to_profile(
            profile=profile,
            first_name=additional_inputs.get("first_name", None),
            last_name=additional_inputs.get("last_name", None),
            middle_name=additional_inputs.get("middle_name", None),
        )
        user.practitioner_profile = profile
        db.session.add(profile)
    elif role not in {*(r.name for r in user.roles)}:
        log.debug("Adding role to user", role_name=role.name, user_id=user.id)
        user.roles.append(role)
        db.session.add(role)
    else:
        log.info(
            "Profile for role already in profiles for user",
            role_name=role.name,
            user_id=user.id,
        )

    return user


def add_name_information_to_profile(
    profile: MemberProfile | PractitionerProfile,
    first_name: Optional[str],
    last_name: Optional[str],
    middle_name: Optional[str],
) -> None:
    if first_name:
        profile.first_name = first_name
    if last_name:
        profile.last_name = last_name
    if middle_name:
        profile.middle_name = middle_name


def set_date_of_birth(
    health_profile: HealthProfile, date_of_birth: Any
) -> HealthProfile:
    try:
        if isinstance(date_of_birth, datetime):
            dob_date = date_of_birth.date()
        elif isinstance(date_of_birth, date):
            dob_date = date_of_birth
        elif isinstance(date_of_birth, str):
            dob_date = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        else:
            raise ValueError("date_of_birth must be datetime/date or str")
    except Exception:
        exc_message = "Exception encountered while trying to parse date of birth"
        log.exception(exc_message, exc=format_exc())
        raise Exception(exc_message)
    else:
        health_profile.birthday = dob_date

    return health_profile


def set_country_and_state(
    member_profile: MemberProfile, country: Optional[str], state: Optional[str]
) -> MemberProfile:
    country_repo = CountryRepository(session=db.session)

    if country:
        country_obj = country_repo.get(country_code=country)
        if country_obj:
            member_profile.country_code = country_obj.alpha_2
        else:
            log.info(f"Country '{country}' not found")

    if state:
        state_obj = (
            db.session.query(State).filter(State.abbreviation == state).one_or_none()
        )
        if state_obj:
            member_profile.state = state_obj
        else:
            log.info(f"State '{state}' not found")

    return member_profile
