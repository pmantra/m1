from __future__ import annotations

import datetime
import itertools
import random
from operator import attrgetter
from typing import Dict, List

from ddtrace import tracer
from maven import feature_flags
from redis.lock import Lock
from sqlalchemy.orm import contains_eager

from authn.models.user import User
from care_advocates.models.assignable_advocates import AssignableAdvocate
from common import stats
from common.services.api import chunk
from models.profiles import (
    CareTeamTypes,
    MemberPractitionerAssociation,
    PractitionerProfile,
)
from models.tracks import TrackName
from models.tracks.client_track import TrackModifiers
from models.tracks.member_track import MemberTrack
from provider_matching.models.constants import StateMatchType
from provider_matching.models.practitioner_track_vgc import PractitionerTrackVGC
from provider_matching.models.vgc import VGC
from provider_matching.services.matching_engine import (
    calculate_state_match_type_for_practitioners_v3,
    get_practitioner_profile,
)
from providers.service.provider import ProviderService
from storage.connection import db
from tasks.queues import job
from tracks.utils.common import get_active_member_track_modifiers
from utils.cache import redis_client
from utils.log import logger
from utils.mail import send_message
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)

DOULA_ONLY_PRIORITY_TRACKS = [
    TrackName.PARTNER_NEWPARENT,
    TrackName.PREGNANCYLOSS,
    TrackName.PREGNANCY_OPTIONS,
]


@tracer.wrap()
@stats.timed(
    metric_name="provider_matching.services.care_team_assignment.ensure_care_advocate.timer",
    pod_name=stats.PodNames.CARE_DISCOVERY,
)
def ensure_care_advocate(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user, multitrack_onboarding=False, force_ca_replacement=False
) -> bool:
    """
    TO-DO: Change method signature should be replace_care_advocate()

    Replaces care advocate for user.
    CA will not be replaced if user already has one they know and trust,
    which we know happens when they are enrolling in an additional track.
    We do want to replace the CA if a user has multiple tracks at onboarding.

    Params:
        user: user for which the care advocate will be replaced
        multitrack_onboarding: True if a user is onboarding with
            multiple tracks, False if not
    Returns:
        True if CA was added or replaced, False if not.
    """
    if (
        len(user.member_tracks) > 1
        and user.care_coordinators
        and not multitrack_onboarding
        and not force_ca_replacement
    ):
        log.info(
            "User has multiple tracks and already has a CA assigned, also we are not enforcing CA replacement",
            user_id=user.id,
            practitioner_id=user.care_coordinators[0].id,
        )
        return False
    AssignableAdvocate.replace_care_coordinator_for_member(user)
    return True


@tracer.wrap()
def replace_care_team_members_during_transition(user: User) -> None:
    log.info(
        "Replacing care team members during a track transition",
        user_id=user.id,
    )
    inactive_tracks_ids = [member_track.id for member_track in user.inactive_tracks]
    member_practitioner_association_ids_for_inactive_tracks = [
        member_practitioner_association.id
        for member_practitioner_association in user.practitioner_associations
        if member_practitioner_association.member_track_id in inactive_tracks_ids
    ]

    # delete all QUIZ-type practitioner associations (associations created at onboarding) for the inactive tracks
    number_of_member_practitioner_associations_deleted = (
        MemberPractitionerAssociation.query.filter(
            MemberPractitionerAssociation.id.in_(
                member_practitioner_association_ids_for_inactive_tracks
            ),
            MemberPractitionerAssociation.type == CareTeamTypes.QUIZ,
        ).delete(synchronize_session="fetch")
    )

    active_tracks = user.active_tracks

    # delete all practitioner associations for practitioners with whom the member can no longer interact from the inactive tracks
    track_modifiers = get_active_member_track_modifiers(active_tracks)
    client_track_ids = [track.client_track_id for track in active_tracks]
    member_practitioner_associations_for_inactive_tracks = (
        MemberPractitionerAssociation.query.filter(
            MemberPractitionerAssociation.id.in_(
                member_practitioner_association_ids_for_inactive_tracks
            ),
        ).all()
    )
    number_of_member_practitioner_associations_deleted += MemberPractitionerAssociation.query.filter(
        MemberPractitionerAssociation.id.in_(
            [
                member_practitioner_association.id
                for member_practitioner_association in member_practitioner_associations_for_inactive_tracks
                if not ProviderService.provider_can_member_interact(
                    provider=member_practitioner_association.practitioner_profile,
                    modifiers=track_modifiers,
                    client_track_ids=client_track_ids,
                )
            ]
        )
    ).delete(
        synchronize_session="fetch"
    )

    log.info(
        "Removed onboarding (quiz-type) and non-interactable member practitioner associations from inactive track.",
        user_id=user.id,
        inactive_track_ids=inactive_tracks_ids,
        number_of_member_practitioner_associations_deleted=number_of_member_practitioner_associations_deleted,
    )

    log.info(
        "Deleting rows in MemberPractitionerAssociation",
        user_id=user.id,
    )
    db.session.expire(user, ["practitioner_associations"])

    for mt in user.active_tracks:
        assign_user_care_team_by_track(user, mt)


@tracer.wrap()
def replace_care_team_members_during_onboarding(user: User) -> None:
    log.info(
        "Replacing care team members during onboarding",
        user_id=user.id,
    )
    number_of_member_practitioner_associations_deleted = (
        MemberPractitionerAssociation.query.filter(
            MemberPractitionerAssociation.user_id == user.id,
            MemberPractitionerAssociation.type == CareTeamTypes.QUIZ,
        ).delete(synchronize_session="fetch")
    )
    log.info(
        "Removed all onboarding (quiz) MPAs for user",
        user_id=user.id,
        number_of_member_practitioner_associations_deleted=number_of_member_practitioner_associations_deleted,
    )

    log.info(
        "Deleting rows in MemberPractitionerAssociation",
        user_id=user.id,
    )
    db.session.expire(user, ["practitioner_associations"])

    for mt in user.active_tracks:
        assign_user_care_team_by_track(user, mt)


@tracer.wrap()
def get_active_practitioners_per_vgc_for_track(
    track_name: str,
    track_modifiers: List[TrackModifiers],
    client_track_ids: List[int],
    member: User,
) -> Dict[str, List[int]]:
    candidate_practitioner_track_vgcs = (
        db.session.query(PractitionerTrackVGC)
        .join(PractitionerProfile)
        .options(contains_eager(PractitionerTrackVGC.practitioner))
        .filter(PractitionerProfile.active == True)
        .filter(PractitionerTrackVGC.track == track_name)
        .order_by(PractitionerTrackVGC.vgc)
        .all()
    )

    active_practitioner_track_vgc: List[PractitionerTrackVGC] = []
    for practitioner_track_vgc in candidate_practitioner_track_vgcs:
        if (
            practitioner_track_vgc.vgc == VGC.DOULA.value
            and TrackModifiers.DOULA_ONLY not in track_modifiers
            and track_name in DOULA_ONLY_PRIORITY_TRACKS
        ):
            continue

        # For US members, we do not want to match them with international providers
        enable_filtering_out_intl_providers = feature_flags.bool_variation(
            "enable-filter-out-intl-providers-for-us-members",
            default=False,
        )
        if (
            not member.member_profile.is_international
            and practitioner_track_vgc.practitioner.is_international
            and enable_filtering_out_intl_providers
        ):
            continue

        # Only add practitioners with whom the member can interact
        if ProviderService.provider_can_member_interact(
            provider=practitioner_track_vgc.practitioner,
            modifiers=track_modifiers,
            client_track_ids=client_track_ids,
        ):
            active_practitioner_track_vgc.append(practitioner_track_vgc)

    practitioner_ids_by_vgc = {
        vgc: [practitioner.practitioner_id for practitioner in practitioner_group]
        for vgc, practitioner_group in itertools.groupby(
            active_practitioner_track_vgc, attrgetter("vgc")
        )
    }

    return practitioner_ids_by_vgc


@tracer.wrap()
def get_practitioner_with_in_state_prioritization(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user: User, prac_ids, track_name, vgc
):
    practitioners_state_match = calculate_state_match_type_for_practitioners_v3(
        user=user, practitioners_ids=prac_ids
    )

    log.info(
        "Computed practitioners_state_match",
        user_id=user.id,
        practitioners_ids=prac_ids,
        user_state=user.member_profile.state if user.member_profile else None,
        practitioners_state_match=practitioners_state_match,
        vgc=vgc,
    )
    n_prac_in_state = len(practitioners_state_match[StateMatchType.IN_STATE.value])
    n_prac_out_of_state = len(
        practitioners_state_match[StateMatchType.OUT_OF_STATE.value]
    )
    n_prac_missing_state = len(practitioners_state_match[StateMatchType.MISSING.value])

    if n_prac_in_state + n_prac_out_of_state + n_prac_missing_state == 0:
        stats.increment(
            metric_name="provider_matching.services.care_team_assignment.assign_user_care_team_by_track.empty_practitioners_state_match",
            pod_name=stats.PodNames.CARE_DISCOVERY,
            tags=[
                f"vgc:{vgc}",
                f"track_name:{track_name}",
            ],
        )
        return None

    if n_prac_in_state > 0:
        potential_practitioner_id = random.choice(
            practitioners_state_match[StateMatchType.IN_STATE.value]
        )
        stats.increment(
            metric_name="provider_matching.services.care_team_assignment.assign_user_care_team_by_track.found_in_state_match",
            pod_name=stats.PodNames.CARE_DISCOVERY,
            tags=[
                f"vgc:{vgc}",
                f"track_name:{track_name}",
            ],
        )
    else:
        potential_practitioner_id = random.choice(
            practitioners_state_match[StateMatchType.OUT_OF_STATE.value]
            + practitioners_state_match[StateMatchType.MISSING.value]
        )
        if n_prac_out_of_state > 0:
            stats.increment(
                metric_name="provider_matching.services.care_team_assignment.assign_user_care_team_by_track.found_state_match_not_permissible",
                pod_name=stats.PodNames.CARE_DISCOVERY,
                tags=[
                    f"vgc:{vgc}",
                    f"track_name:{track_name}",
                ],
            )
        else:
            stats.increment(
                metric_name="provider_matching.services.care_team_assignment.assign_user_care_team_by_track.found_missing_state_match",
                pod_name=stats.PodNames.CARE_DISCOVERY,
                tags=[
                    f"vgc:{vgc}",
                    f"track_name:{track_name}",
                ],
            )
    return potential_practitioner_id


def create_dd_metric_for_user_state_data(user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if not user.member_profile:
        stats.increment(
            metric_name="provider_matching.services.care_team_assignment.assign_user_care_team_by_track.user_missing_member_profile",
            pod_name=stats.PodNames.CARE_DISCOVERY,
            tags=[
                f"user_id:{user.id}",
                f"user_type:{'enterprise' if user.is_enterprise else 'marketplace'}",
            ],
        )
    elif not user.member_profile.state:
        stats.increment(
            metric_name="provider_matching.services.care_team_assignment.assign_user_care_team_by_track.user_missing_state",
            pod_name=stats.PodNames.CARE_DISCOVERY,
            tags=[
                f"user_id:{user.id}",
                f"user_type:{'enterprise' if user.is_enterprise else 'marketplace'}",
            ],
        )
    else:
        stats.increment(
            metric_name="provider_matching.services.care_team_assignment.assign_user_care_team_by_track.user_with_state",
            pod_name=stats.PodNames.CARE_DISCOVERY,
            tags=[
                f"user_id:{user.id}",
                f"user_type:{'enterprise' if user.is_enterprise else 'marketplace'}",
            ],
        )


@tracer.wrap()
@stats.timed(
    metric_name="provider_matching.services.care_team_assignment.assign_user_care_team_by_track.timer",
    pod_name=stats.PodNames.CARE_DISCOVERY,
)
def assign_user_care_team_by_track(user: User, member_track: MemberTrack) -> None:
    """
    For every VGC in member_track, we will get the practitioners that
    serve that VGC, and try to add them to the member's care team.

    We will only add a practitioner as long as at least one of it's verticals isn't
    currently covered by the user's care team
    """

    log.info("Assigning care team", user_id=user.id, track_name=member_track.name)

    create_dd_metric_for_user_state_data(user=user)

    # prac_ids_by_vgc are practitioners for every vgc in the member_track
    # that are candidates to be possibly added to the user's care team
    prac_ids_by_vgc = get_active_practitioners_per_vgc_for_track(
        track_name=member_track.name,
        track_modifiers=member_track.track_modifiers,
        client_track_ids=[member_track.client_track_id],
        member=user,
    )
    if not prac_ids_by_vgc:
        log.warn(
            "Found no practitioners for track",
            user_id=user.id,
            track_name=member_track.name,
        )
        if (
            member_track.name != "generic"
        ):  # We know that the generic track has no practitioners, thats fine, dont alert for that one
            stats.increment(
                metric_name="provider_matching.services.care_team_assignment.assign_user_care_team_by_track.no_practitioners_for_track",
                pod_name=stats.PodNames.CARE_DISCOVERY,
                tags=[
                    f"track_name:{member_track.name}",
                ],
            )
        return
    log.info(
        "prac_ids_by_vgc",
        prac_ids_by_vertical=prac_ids_by_vgc,
        track_name=member_track.name,
    )

    # potential_prac_id_per_vgc has only one prac_id for every vgc, who is a candidate to be added to the care team
    potential_prac_id_per_vgc = []

    # using in state matching
    log.info(
        "Selecting potential_practitioners_id_per_vgc with in state matches prioritization"
    )
    # Choose a practitioner from every vgc giving priority to in_state practitioners
    for vgc, prac_ids in prac_ids_by_vgc.items():
        potential_practitioner_id = get_practitioner_with_in_state_prioritization(
            user=user, prac_ids=prac_ids, track_name=member_track.name, vgc=vgc
        )
        if potential_practitioner_id:
            potential_prac_id_per_vgc.append(potential_practitioner_id)

    log.info(
        "Computed potential_prac_id_per_vgc",
        potential_prac_id_per_vgc=potential_prac_id_per_vgc,
    )

    # Get unique verticals of my care team
    # as a way to know which are the verticals that are already covered by my care team
    # (I will not need to add a practitioner for these verticals)

    # Something to note - and confusing - is that this logic uses verticals rather than vgc.
    # Changing that to use vcg is ultimately a product decision so we will leave it as it is for now
    existing_vertical_arrays = [
        prac_profile.verticals for prac_profile in user.care_team if prac_profile
    ]
    existing_verticals = set(itertools.chain(*existing_vertical_arrays))

    # Loop over one practitioner for every vgc to be covered
    for prac_id in potential_prac_id_per_vgc:
        prac_profile = get_practitioner_profile(prac_id)
        if not prac_profile:
            log.warn(
                "Practitioner not found when assigning care team",
                practitioner_id=prac_id,
            )
            stats.increment(
                metric_name="provider_matching.services.care_team_assignment.assign_user_care_team_by_track",
                pod_name=stats.PodNames.CARE_DISCOVERY,
                tags=["error:true", "error_cause:prac_not_found"],
            )
            continue

        # Avoid adding a practitioner if the verticals covered
        # by this practitioner are already covered by my care team
        if all(v in existing_verticals for v in prac_profile.verticals):
            log.info(
                "Practitioners with these verticals already in care team, not adding",
                existing_verticals=existing_verticals,
                new_verticals=prac_profile.verticals,
            )
            continue

        user.add_track_onboarding_care_team_member(
            practitioner_id=prac_id, member_track=member_track
        )

        # Update existing verticals so we dont further add practitioner to cover same verticals
        for v in prac_profile.verticals:
            existing_verticals.add(v)


@tracer.wrap()
def has_member_practitioner_association(prac_id, remove_only_quiz_type):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    users_in_care_teams_query = db.session.query(
        MemberPractitionerAssociation.user_id
    ).filter_by(
        practitioner_id=prac_id,
    )
    if remove_only_quiz_type:
        users_in_care_teams_query = users_in_care_teams_query.filter_by(
            type=CareTeamTypes.QUIZ,
        )
    first_users_in_care_teams = users_in_care_teams_query.first()
    log.info("Querying rows in MemberPractitionerAssociation", practitioner_id=prac_id)

    return first_users_in_care_teams


@tracer.wrap()
def is_an_active_available_practitioner(prac_id: int) -> bool:
    prac_present_in_table = (
        db.session.query(PractitionerTrackVGC).filter_by(practitioner_id=prac_id).all()
    )
    if not prac_present_in_table:
        return False

    prac = db.session.query(PractitionerProfile).get(prac_id)
    return prac.active


@tracer.wrap()
def find_users_associated_to_practitioner(prac_id, remove_only_quiz_type):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # move back into the function
    users_in_care_teams_query = db.session.query(
        MemberPractitionerAssociation.user_id
    ).filter_by(
        practitioner_id=prac_id,
    )
    if remove_only_quiz_type:
        users_in_care_teams_query = users_in_care_teams_query.filter_by(
            type=CareTeamTypes.QUIZ,
        )
    log.info(
        "Querying rows in MemberPractitionerAssociation",
        practitioner_id=prac_id,
    )
    users_ids_in_care_teams = [u.user_id for u in users_in_care_teams_query.distinct()]
    return users_ids_in_care_teams


REPLACE_PRAC_JOB_TIMEOUT = (
    12 * 60
)  # Based on tests in qa, we know that jobs that run for over 12 minutes usually have mysql client connections closed, and no exceptions raised. To avoid that, we will set the job timeout to 12 min
REPLACE_PRAC_N_USERS_PER_JOB = 1000  # Based on tests in qa, a replace_practitioner job with 1000 users would take <5 min which is a reasonable load of work.


@tracer.wrap()
def spin_off_replace_practitioner_in_care_teams_jobs(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    prac_to_replace_id,
    remove_only_quiz_type,
    to_email,
    n_users_per_job=REPLACE_PRAC_N_USERS_PER_JOB,
):
    """
    Spins of jobs to replace a practitioner by other practitioners in all users' care teams where prac_to_replace is present.

    Args
        prac_to_replace: practitioner to be replaced
        remove_only_quiz_type: True if we only want to replace the practitioner when they are type QUIZ
        to_email: email to which to send notification
        n_users_per_job: int to indicate number of users to process in every job
    Returns
        jobs_ids: list with job ids
    """

    log.info(
        "Starting spin_off_replace_practitioner_in_care_teams_jobs",
        prac_to_replace_id=prac_to_replace_id,
        remove_only_quiz_type=remove_only_quiz_type,
    )

    # Identify all users for which the prac_to_replace is present in their care teams.
    users_ids = find_users_associated_to_practitioner(
        prac_to_replace_id, remove_only_quiz_type
    )
    if not users_ids:
        log.error(
            "Found no users associated to practitioner",
            prac_to_replace_id=prac_to_replace_id,
        )
        return
    log.info(
        "Found users associated to practitioner",
        prac_to_replace_id=prac_to_replace_id,
        n_users=len(users_ids),
        users_ids_in_care_teams=users_ids,
    )

    chunks_users_ids = list(chunk(users_ids, n_users_per_job))
    log.info(
        "Computed chunks of user ids to process",
        n_chunks=len(chunks_users_ids),
        chunks_users_ids=chunks_users_ids,
    )

    jobs_ids = []
    for chunk_users_ids in chunks_users_ids:
        service_ns_tag = "care_team"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        job = replace_practitioner_in_care_teams.delay(
            prac_to_replace_id=prac_to_replace_id,
            users_ids=chunk_users_ids,
            remove_only_quiz_type=remove_only_quiz_type,
            to_email=to_email,
            job_timeout=REPLACE_PRAC_JOB_TIMEOUT,
            service_ns=service_ns_tag,
            team_ns=team_ns_tag,
        )
        log.info(
            "Spinning off replace_practitioner_in_care_teams job for chunk of users",
            chunk_users_ids=chunk_users_ids,
            job_id=job.id,
        )
        jobs_ids.append(job.id)

    more_than_one_job = True if len(jobs_ids) > 1 else False
    log.info(
        "Finished spinning off replace_practitioner_in_care_teams jobs",
        jobs_ids=jobs_ids,
        chunks_users_ids=chunks_users_ids,
    )
    email_text = f"""You have launched a request to replace Practitioner ID: {prac_to_replace_id} in all care teams
        {'where the practitioner is present as type Quiz.' if remove_only_quiz_type else '.'}
        {len(users_ids)} users' care teams will be impacted.
        To process this request, {len(jobs_ids)} request{'s have' if more_than_one_job else ' has'} been spun off.
        The Jobs ID{'s are' if more_than_one_job else 'is'} the following: {jobs_ids}"""
    send_message(
        to_email=to_email,
        subject="Replace practitioner request has started",
        text=email_text,
        internal_alert=True,
        production_only=False,
    )
    return jobs_ids


@tracer.wrap()
def remove_member_practitioner_associations(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    prac_to_remove, remove_only_quiz_type, user_id=None
) -> list[int]:
    if user_id:
        mpas_to_delete_query = MemberPractitionerAssociation.query.filter_by(
            practitioner_id=prac_to_remove, user_id=user_id
        )
    else:
        mpas_to_delete_query = MemberPractitionerAssociation.query.filter_by(
            practitioner_id=prac_to_remove
        )
    if remove_only_quiz_type:
        mpas_to_delete_query = mpas_to_delete_query.filter_by(
            type=CareTeamTypes.QUIZ,
        )

    mpa_ids = mpas_to_delete_query.with_entities(MemberPractitionerAssociation.id).all()

    mpas_to_delete = [id for (id,) in mpa_ids]

    db.session.query(MemberPractitionerAssociation.id).filter(
        MemberPractitionerAssociation.id.in_(mpas_to_delete)
    ).delete(synchronize_session="fetch")
    log.info(
        "Deleting rows in MemberPractitionerAssociation",
        practitioner_id=prac_to_remove,
        user_id=user_id,
    )

    return mpas_to_delete


@job("priority")
def replace_practitioner_in_care_teams(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    prac_to_replace_id: int,
    users_ids: List[int],
    remove_only_quiz_type: bool,
    to_email: str,
):
    """
    Replace a practitioner by other practitioners in certain users's care teams.

    Args
        prac_to_replace: practitioner to be replaced
        users_ids: users for which the replacement must happen
        remove_only_quiz_type: True if we only want to replace the practitioner when they are type QUIZ
        to_email: email to which to send notification
    """
    job_start_time = datetime.datetime.now()
    log.info(
        "Starting process to replace practitioner in care teams",
        prac_to_replace_id=prac_to_replace_id,
        users_ids=users_ids,
        remove_only_quiz_type=remove_only_quiz_type,
        date_time=str(job_start_time),
    )

    users_ids_with_successful_replacement = []
    try:
        # For each user, remove their associations with prac_to_replace and re-assign them a care team
        for user_id in users_ids:
            # Delete the associations
            mpas_deleted = remove_member_practitioner_associations(
                prac_to_remove=prac_to_replace_id,
                user_id=user_id,
                remove_only_quiz_type=remove_only_quiz_type,
            )
            if len(mpas_deleted) > 0:
                log.info(
                    "Deleted MemberPractitionerAssociation rows",
                    mpas_ids=mpas_deleted,
                    user_id=user_id,
                    practitioner_id=prac_to_replace_id,
                )
            else:
                log.error(
                    "No MemberPractitionerAssociation rows found",
                    user_id=user_id,
                    practitioner_id=prac_to_replace_id,
                )
                continue

            user_in_care_team = db.session.query(User).get(user_id)
            db.session.expire(user_in_care_team, ["practitioner_associations"])

            log.info(
                "Starting to assign user care teams for user",
                user_id=user_id,
            )
            for track in user_in_care_team.active_tracks:
                assign_user_care_team_by_track(user_in_care_team, track)

            log.info("Committing replace_practitioner_in_care_teams changes to db")
            db.session.commit()

            users_ids_with_successful_replacement.append(user_id)

        send_message(
            to_email=to_email,
            subject="Practitioner replacement completed for group of users",
            text=f"Practitioner ID: {prac_to_replace_id} was removed from {len(users_ids)} care teams. Users IDs where practitioner was replaced: {users_ids}",
            internal_alert=True,
            production_only=False,
        )
        job_end_time = datetime.datetime.now()
        job_duration = job_end_time - job_start_time
        log.info(
            "Practitioner replacement completed for group of users. Email sent current user.",
            prac_to_replace=prac_to_replace_id,
            users_ids=users_ids,
            n_users=len(users_ids),
            date_time=str(job_end_time),
            job_duration=str(job_duration),
        )

        # If this is the last job running for this replacement task, we should release the practitoner_id lock
        if has_member_practitioner_association(
            prac_to_replace_id, remove_only_quiz_type
        ):
            log.info("Not all jobs have finished, holding lock")
        else:
            log.info(
                "No more MPAs for this practitioners, all jobs have finished, releasing lock"
            )
            redis = redis_client()
            lock_name = f"{prac_to_replace_id}_replace_practitioner_in_progress"
            lock = Lock(
                redis=redis,
                name=lock_name,
                timeout=REPLACE_PRAC_JOB_TIMEOUT,
            )
            if lock.locked():
                lock.do_release(expected_token=str(prac_to_replace_id))
                log.info("Lock released", lock_token=str(prac_to_replace_id))
            else:
                log.error(
                    "Trying to release a lock that is not locked",
                    lock_name=lock_name,
                    lock_token=str(prac_to_replace_id),
                )

    except Exception as e:
        log.error(
            "Exception when running replace_practitioner_in_care_teams", exception=e
        )
        db.session.rollback()
        if len(users_ids_with_successful_replacement) == 0:
            email_text = f"Practitioner ID {prac_to_replace_id} was not removed from any care teams. Error: {e}"
            log_message = "Practitioner replacement failed for all care teams. Email sent to user."
        else:
            email_text = f"""Practitioner ID {prac_to_replace_id} was not removed from all user care teams in group of users.
                Practitioner was successfully removed from the following users' care teams: {users_ids_with_successful_replacement}
                Practitioner was not removed from the following users' care teams: {[u for u in users_ids if u not in users_ids_with_successful_replacement]}
                Error: {e}"""
            log_message = "Practitioner replacement failed for some users's care teams. Email sent to user."

        notification_title = "Practitioner replacement failed"
        send_message(
            to_email=to_email,
            subject=notification_title,
            text=email_text,
            internal_alert=True,
            production_only=False,
        )
        log.error(
            log_message,
            to_email=to_email,
            prac_to_replace=prac_to_replace_id,
            users_ids=users_ids,
            users_ids_with_successful_replacement=users_ids_with_successful_replacement,
            error=e,
            date_time=str(datetime.datetime.now()),
        )
