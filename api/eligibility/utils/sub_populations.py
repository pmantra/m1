from typing import Dict

from eligibility import service as e9y_service
from models.tracks import client_track, member_track
from storage.connection import db


def backfill_org_sub_populations(
    organization_id: int, overwrite_all: bool = False, no_op: bool = True
) -> Dict[int, int]:
    """
    Backfills the sub-population ID for active member tracks of the specified organization by
    connecting to the Eligibility service to get the sub-population ID for the user.

    The overwrite_all flag will cause the sub-population IDs to be updated for all active
    member tracks. In most cases, this is unnecessary. Typically, this function will be used
    to backfill organizations that recently had its configuration set, so the intent would
    be to set member tracks that were created prior to the sub-population configuration
    set. The overwrite_all flag can be used if there was an error in the configuration and
    member tracks have been created with incorrect assignments due to the error.

    The no_op flag determines whether or not to write the sub-population IDs to the database.
    The parameter is enabled by default as a precaution. By running the function without
    updating the database, this allows the user to review the changes that would be applied.
    """
    the_query = member_track.MemberTrack.query.join(
        client_track.ClientTrack,
        member_track.MemberTrack.client_track_id == client_track.ClientTrack.id,
    ).filter(
        member_track.MemberTrack.active.is_(True),
        client_track.ClientTrack.organization_id == organization_id,
    )
    if not overwrite_all:
        the_query = the_query.filter(member_track.MemberTrack.sub_population_id == None)
    unassigned_member_tracks = the_query.all()

    e9y_svc = e9y_service.EnterpriseVerificationService()
    sub_pop_map = {}
    for m_track in unassigned_member_tracks:
        if m_track.user_id == 0:
            continue
        if m_track.user_id not in sub_pop_map:
            sub_pop_map[
                m_track.user_id
            ] = e9y_svc.get_sub_population_id_for_user_and_org(
                user_id=m_track.user_id, organization_id=organization_id
            )
        sub_pop_id = sub_pop_map.get(m_track.user_id, None)
        if not no_op:
            m_track.sub_population_id = sub_pop_id
    if not no_op:
        db.session.commit()
    return sub_pop_map
