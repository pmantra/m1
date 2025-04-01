from typing import List

import ddtrace
from sqlalchemy.orm import Load

from authn.models.user import User
from incentives.models.incentive import (
    Incentive,
    IncentiveAction,
    IncentiveOrganization,
    IncentiveOrganizationCountry,
    IncentiveType,
)
from models.enterprise import Organization
from models.tracks import MemberTrack
from models.tracks.client_track import ClientTrack
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class IncentiveOrganizationRepository:
    @ddtrace.tracer.wrap()
    def get_by_params(self, organization_id, incentive_type, track, action):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Return incentive organization by params
        """
        incentive_org = (
            db.session.query(IncentiveOrganization)
            .filter(
                IncentiveOrganization.organization_id == organization_id,
                IncentiveOrganization.track_name == track,
                IncentiveOrganization.active == True,
                IncentiveOrganization.action == action,
            )
            .join(Incentive, Incentive.id == IncentiveOrganization.incentive_id)
            .filter(Incentive.type == incentive_type)
            .first()
        )

        return incentive_org

    @ddtrace.tracer.wrap()
    def get_offboarding_incentive_orgs_for_org(self, organization_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # get all active offboarding assessment incentives for this org
        return (
            db.session.query(
                IncentiveOrganization.id,
                IncentiveOrganization.organization_id,
                IncentiveOrganization.incentive_id,
                IncentiveOrganization.track_name,
                IncentiveOrganizationCountry.country_code,
            )
            .filter(
                IncentiveOrganization.active == True,
                IncentiveOrganization.action
                == IncentiveAction.OFFBOARDING_ASSESSMENT.name,
                IncentiveOrganization.organization_id == organization_id,
            )
            .join(IncentiveOrganizationCountry)
            .all()
        )

    @ddtrace.tracer.wrap()
    def get_org_users_with_potential_offboarding_incentives(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, organization_id: int, offboarding_incentive_tracks: List[str]
    ):
        return (
            db.session.query(User)
            .filter(
                User.active == True,
                User.country_code != None,
            )
            .join(MemberTrack)
            .filter(
                MemberTrack.ended_at == None,
                MemberTrack.name.in_(offboarding_incentive_tracks),
            )
            .join(ClientTrack)
            .join(Organization)
            .filter(
                Organization.id == organization_id,
            )
            .options(
                Load(MemberTrack).load_only(  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
                    MemberTrack.ended_at,
                ),
            )
            .all()
        )

    @ddtrace.tracer.wrap()
    def get_incentive_orgs_by_incentive_type_and_org(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, organization_id: int, incentive_type: IncentiveType
    ):
        incentive_orgs_query = db.session.query(IncentiveOrganization).filter(
            IncentiveOrganization.organization_id == organization_id,
            IncentiveOrganization.active == True,
        )
        if incentive_type != "ALL":
            incentive_orgs_query = incentive_orgs_query.join(Incentive).filter(
                Incentive.type == incentive_type
            )
        return incentive_orgs_query.all()

    def get_incentive_orgs_by_track_action_and_active_status(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, track_name: str, action: str, is_active: bool
    ):
        query = db.session.query(IncentiveOrganization).filter(
            IncentiveOrganization.track_name == track_name,
            IncentiveOrganization.action == action,
            IncentiveOrganization.active == is_active,
        )

        return query.all()
