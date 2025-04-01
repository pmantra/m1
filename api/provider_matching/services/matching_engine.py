from typing import List, Optional

from ddtrace import tracer
from maven import feature_flags
from maven.feature_flags import bool_variation

from authn.models.user import User
from models.base import db
from models.profiles import (
    PractitionerProfile,
    practitioner_states,
    practitioner_verticals,
)
from models.verticals_and_specialties import Vertical
from provider_matching.models.constants import StateMatchType
from provider_matching.services.constants import COUNTRY_REGION_MAPPING
from providers.service.provider import ProviderService
from utils.launchdarkly import user_context
from utils.log import logger

log = logger(__name__)


@tracer.wrap()
def get_practitioner_profile(practitioner_id: int) -> PractitionerProfile:
    return PractitionerProfile.query.get(practitioner_id)


@tracer.wrap()
def calculate_state_match_type(
    practitioner_profile: "PractitionerProfile", user: "User"
) -> str:
    """
    Determine the state match type
    """
    if user.member_profile and (
        not practitioner_profile.certified_states or not user.member_profile.state
    ):
        return StateMatchType.MISSING.value
    elif user.member_profile and ProviderService().in_certified_states(
        practitioner_profile.user_id,
        user.member_profile.state,
        provider=practitioner_profile,
    ):
        return StateMatchType.IN_STATE.value
    else:
        return StateMatchType.OUT_OF_STATE.value


def get_user_region(user: User) -> Optional[str]:
    country_code = user.member_profile.country_code

    if not country_code:
        return None

    return COUNTRY_REGION_MAPPING.get(country_code)


def member_is_international(user: User) -> bool:
    return user.member_profile.is_international


@tracer.wrap()
def get_vertical_country_or_region_matched_practitioners(
    user: User, practitioners_ids: List[int]
) -> list:
    region = get_user_region(user)

    if not region:
        return []

    # Query practitioners with the right vertical
    prac_verticals_of_interest = (
        db.session.query(PractitionerProfile)
        .join(
            practitioner_verticals,
            PractitionerProfile.user_id == practitioner_verticals.c.user_id,
        )
        .join(Vertical, practitioner_verticals.c.vertical_id == Vertical.id)
        .filter(
            PractitionerProfile.user_id.in_(practitioners_ids),
            Vertical.region == region,
        )
        .all()
    )
    # If there is a practitioner within the same country as the user, return only practitioners from that country
    prac_of_interest_in_same_country = []
    for prac in prac_verticals_of_interest:
        if user.country_code == prac.country_code:
            prac_of_interest_in_same_country.append(prac)

    if prac_of_interest_in_same_country:
        return prac_of_interest_in_same_country

    # If there is no practitioner from the same country, return the practitioners from the same region
    return prac_verticals_of_interest


@tracer.wrap()
def calculate_state_match_type_for_practitioners_v3(user, practitioners_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    matches = {
        StateMatchType.IN_STATE.value: [],
        StateMatchType.OUT_OF_STATE.value: [],
        StateMatchType.MISSING.value: [],
    }

    # Check if user's state is missing
    if not user.member_profile or not user.member_profile.state:
        matches[StateMatchType.MISSING.value] = practitioners_ids
        return matches

    enable_i18n_care_team_creation = feature_flags.bool_variation(
        "release-automate-international-care-team-creation",
        user_context(user),
        default=False,
    )

    if enable_i18n_care_team_creation and member_is_international(user):
        pracs_of_interest = get_vertical_country_or_region_matched_practitioners(
            user=user, practitioners_ids=practitioners_ids
        )

        # We consider matched international practitioner as "in state"
        # Otherwise they are considered "out of state"
        # If we don't find any matching international practitioner, continue with the old matching mechanism
        # doc:  https://docs.google.com/document/d/1nXasBVvNNnPIzZbB2X3OwD28wRc8wuThvdkYefHI240/edit?tab=t.0#heading=h.i8tqqbk5nd2a
        if pracs_of_interest:
            in_state_prac_ids = [prac.user_id for prac in pracs_of_interest]
            matches[StateMatchType.IN_STATE.value] = in_state_prac_ids
            matches[StateMatchType.OUT_OF_STATE.value] = [
                prac_id
                for prac_id in practitioners_ids
                if prac_id not in in_state_prac_ids
            ]
            return matches

    # Get practitioners-states associations for practitioners_ids
    prac_states_of_interest = (
        db.session.query(practitioner_states)
        .filter(practitioner_states.c.user_id.in_(practitioners_ids))
        .all()
    )

    # Loop over prac_states_of_interest, check their state and save them in the in_state or out_of_state sets
    # We could have duplicates in out_of_state (pracs that work in two states different from the user's state)
    in_state: set = set()
    out_of_state: set = set()
    for ps in prac_states_of_interest:
        if ps.state_id == user.member_profile.state.id:
            in_state.add(ps.user_id)
        else:
            out_of_state.add(ps.user_id)

    # We could have pracs that are in state and out of state at the same time, so we've got to remove those
    out_of_state -= in_state

    no_state = [
        p_id
        for p_id in practitioners_ids
        if p_id not in in_state and p_id not in out_of_state
    ]

    matches[StateMatchType.IN_STATE.value] = list(in_state)
    matches[StateMatchType.OUT_OF_STATE.value] = list(out_of_state)
    matches[StateMatchType.MISSING.value] = no_state

    return matches


class StateMatchNotPermissibleError(Exception):
    ...


class StateMatchNotPermissibleMessage(str):
    PRACTITIONER_HAS_NO_VERTICALS = "Practitioner has no verticals"
    VERTICAL_FILTER_BY_STATE_AND_NO_CERTIFIED_STATES = "Practitioner's vertical is filter_by_state True but Practitioner is not certified in any state"
    USER_HAS_NO_STATE = "User has no state"
    VERTICAL_FILTER_BY_STATE_IS_FALSE = (
        "Practitioner's vertical filter_by_state is False"
    )
    USER_STATE_IN_CERTIFIED_STATES = (
        "User's state is in practitioner_profile.certified_states"
    )
    USER_STATE_NOT_IN_IN_STATE_MATCHING_STATES = (
        "User's state not listed in vertical.in_state_matching_states"
    )
    FOUND_NOT_PERMISSIBLE_STATE_MATCH = "Found a not permissible state match"


@tracer.wrap()
def state_match_not_permissible(practitioner_profile, user, product=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    A state match is not permitted when these 3 conditions are met:
    * The practitioner's vertical is filter by state: true
    * The user's state is not part of the states where the provider is certified
    * The user's state is listed in the vertical_in_state_match_state table for the provider's vertical

    The practitioner's vertical should never be missing. If that's the case we will raise an error to the user
    The practitioner's certified states should never be empty for a practitioner whose vertical is filter_by_state True. If that's the case we will raise an error to the user
    If the user's state is missing, we will consider that a permissible match

    Note: No practioners currently have multiple verticals, but it's possible for them to do so. Getting vertical from
    product instead of practitioner_profile ensures the vertical is associated with the product we are looking for. If
    we are not passed a product, we default to practitioner_profile.verticals[0].
    """

    if len(practitioner_profile.verticals) == 0 and not product:
        error_msg = StateMatchNotPermissibleMessage.PRACTITIONER_HAS_NO_VERTICALS
        log.warn(
            error_msg,
            practitioner_id=practitioner_profile.user_id,
        )
        raise StateMatchNotPermissibleError(error_msg)

    # added to handle a practitioner having multiple verticals
    vertical = product.vertical if product else practitioner_profile.verticals[0]

    relax_certified_state_check = bool_variation(
        "relax-certified-state-check", default=False
    )
    if not relax_certified_state_check:
        if (
            vertical.filter_by_state is True
            and len(practitioner_profile.certified_states) == 0
        ):
            error_msg = (
                StateMatchNotPermissibleMessage.VERTICAL_FILTER_BY_STATE_AND_NO_CERTIFIED_STATES
            )
            log.warn(
                error_msg,
                practitioner_id=practitioner_profile.user_id,
                vertical_id=vertical.id,
            )
            raise StateMatchNotPermissibleError(error_msg)

    if user.member_profile.state is None:
        log.info(StateMatchNotPermissibleMessage.USER_HAS_NO_STATE, user_id=user.id)
        return False
    elif vertical.filter_by_state is False:
        log.info(
            StateMatchNotPermissibleMessage.VERTICAL_FILTER_BY_STATE_IS_FALSE,
            vertical_id=vertical.id,
        )
        return False
    elif user.member_profile.state in practitioner_profile.certified_states:
        log.info(
            StateMatchNotPermissibleMessage.USER_STATE_IN_CERTIFIED_STATES,
            users_state=user.member_profile.state,
            practitioners_certified_states=practitioner_profile.certified_states,
        )
        return False
    elif user.member_profile.state not in vertical.in_state_matching_states:
        log.info(
            StateMatchNotPermissibleMessage.USER_STATE_NOT_IN_IN_STATE_MATCHING_STATES,
            users_state=user.member_profile.state,
            vertical_id=vertical.id,
            verticals_in_state_matching_states=vertical.in_state_matching_states,
        )
        return False

    elif (
        user.member_profile.state
        and len(practitioner_profile.verticals) > 0
        and vertical.filter_by_state is True
        and user.member_profile.state not in practitioner_profile.certified_states
        and user.member_profile.state in vertical.in_state_matching_states
    ):
        log.info(
            StateMatchNotPermissibleMessage.FOUND_NOT_PERMISSIBLE_STATE_MATCH,
            users_state=user.member_profile.state,
            practitioners_certified_states=practitioner_profile.certified_states,
            vertical_id=vertical.id,
            verticals_in_state_matching_states=vertical.in_state_matching_states,
        )
        return True
    # We should never get to this place without returning, the last elif should be equal to an else statement
    else:
        # NB: The comment above was added on 11/29/22. As of 5/28/2024, logging confirms that we do indeed
        # reach this point without returning, so we did return None. Instead, let's
        log.error(
            "Invalid system state:",
            users_state=user.member_profile.state,
            practitioners_certified_states=practitioner_profile.certified_states,
            vertical_id=vertical.id,
            verticals_in_state_matching_states=vertical.in_state_matching_states,
        )
        raise StateMatchNotPermissibleError("Invalid system state")
