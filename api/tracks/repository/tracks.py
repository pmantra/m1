from __future__ import annotations

from typing import List

import ddtrace.ext
import sqlalchemy as sa
import sqlalchemy.orm.scoping

from eligibility import service as e9y_service
from eligibility.e9y import model as e9y_model
from models.tracks import ClientTrack, MemberTrack
from storage import connection
from utils.log import logger
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)

log = logger(__name__)

__all__ = ("TracksRepository",)

trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class TracksRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.session = session or connection.db.session

    def get_client_track(
        self, *, organization_id: int, track: str, active_only: bool = False
    ) -> ClientTrack | None:
        query: sqlalchemy.orm.Query = self.session.query(ClientTrack).filter_by(
            track=track, organization_id=organization_id
        )
        if active_only:
            query = query.filter(
                ClientTrack.active == sa.true(),
                sa.func.coalesce(ClientTrack.launch_date, sa.func.current_date())
                <= sa.func.current_date(),
            )

        return query.first()

    def get_active_tracks(self, *, organization_id: int) -> List[ClientTrack]:
        """
        Get all active tracks for an organization.
        Tracks that are configured and active for an org.
        """
        query: sqlalchemy.orm.Query = self.session.query(ClientTrack).filter(
            ClientTrack.organization_id == organization_id,
            ClientTrack.active == sa.true(),
            sa.func.coalesce(ClientTrack.launch_date, sa.func.current_date())
            <= sa.func.current_date(),
        )
        results: List[ClientTrack] = query.all()
        return results

    def get_all_enrolled_tracks(
        self, *, user_id: int, active_only: bool = True
    ) -> List[MemberTrack]:
        """
        Get the tracks that this user is currently enrolled for, regardless of org
        By default, only return active tracks
        """

        query: sqlalchemy.orm.Query = (
            self.session.query(MemberTrack)
            .join(ClientTrack)
            .filter(MemberTrack.user_id == user_id)
        )

        if active_only:
            query = query.filter(MemberTrack.active == active_only)

        results: List[MemberTrack] = query.order_by(MemberTrack.created_at.desc()).all()
        return results

    def get_enrolled_tracks(
        self, *, user_id: int, organization_id: int
    ) -> List[MemberTrack]:
        """
        Get the tracks that this user is currently enrolled in for this org.
        Tracks that are currently in-progress for a user for a specific org.
        """
        query: sqlalchemy.orm.Query = (
            self.session.query(MemberTrack)
            .join(ClientTrack)
            .filter(
                MemberTrack.user_id == user_id,
                MemberTrack.active == sa.true(),
                ClientTrack.organization_id == organization_id,
            )
        )
        results: List[MemberTrack] = query.all()
        return results

    def _build_available_tracks_query(
        self, *, user_id: int, organization_ids: List[int], client_track_ids: List[int]
    ) -> sqlalchemy.orm.Query:
        query: sqlalchemy.orm.Query = (
            self.session.query(ClientTrack)
            .outerjoin(
                MemberTrack,
                sa.and_(
                    ClientTrack.id == MemberTrack.client_track_id,
                    MemberTrack.active == sa.true(),
                    MemberTrack.user_id == user_id,
                ),
            )
            .filter(
                ClientTrack.organization_id.in_(organization_ids),
                ClientTrack.active == sa.true(),
                sa.func.coalesce(ClientTrack.launch_date, sa.func.current_date())
                <= sa.func.current_date(),
                MemberTrack.id == sa.null(),
            )
        )
        if client_track_ids is not None:
            query = query.filter(ClientTrack.id.in_(client_track_ids))
        return query

    def get_available_tracks(
        self, *, user_id: int, organization_id: int
    ) -> List[ClientTrack]:
        """
        Get the tracks that are currently available for a user who is enrolled under a specific org.
        (excludes active enrolled tracks)
        NOTE: we are filtering by organization_id here to account for future multi-org support
        """
        e9y_svc = e9y_service.get_verification_service()
        client_track_ids = e9y_svc.get_eligible_features_for_user_and_org(
            user_id=user_id,
            organization_id=organization_id,
            feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
        )

        log.info(
            f"Eligible features for user and org: {client_track_ids}",
            user_id=user_id,
            organization_id=organization_id,
            feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
        )
        query = self._build_available_tracks_query(
            user_id=user_id,
            organization_ids=[organization_id],
            client_track_ids=client_track_ids,
        )

        results: List[ClientTrack] = query.all()

        return results

    def get_all_available_tracks(
        self, *, user_id: int, organization_ids: List[int]
    ) -> List[ClientTrack]:
        """
        Get the tracks that are currently available for a user who is enrolled under a specific org list.
        (excludes active enrolled tracks)
        """
        e9y_svc = e9y_service.get_verification_service()
        client_track_ids = e9y_svc.get_eligible_features_for_user(
            user_id=user_id,
            feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
        )
        log.info(
            f"Eligible features for user: {client_track_ids}",
            user_id=user_id,
            feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
        )
        query = self._build_available_tracks_query(
            user_id=user_id,
            organization_ids=organization_ids,
            client_track_ids=client_track_ids,
        )
        results: List[ClientTrack] = query.all()
        return results

    def get_all_client_tracks(
        self, *, user_id: int, organization_id: int
    ) -> List[ClientTrack]:
        """
        Get the tracks for an organization that a user is currently eligible for.
        (excludes tracks they are currently enrolled in)

        NOTE: we are filtering by organization_id here to account for future multi-org support
        """
        query: sqlalchemy.orm.Query = (
            self.session.query(ClientTrack)
            .outerjoin(
                MemberTrack,
                sa.and_(
                    ClientTrack.id == MemberTrack.client_track_id,
                    MemberTrack.active == sa.true(),
                    MemberTrack.user_id == user_id,
                ),
            )
            .filter(
                ClientTrack.organization_id == organization_id,
                ClientTrack.active == sa.true(),
                sa.func.coalesce(ClientTrack.launch_date, sa.func.current_date())
                <= sa.func.current_date(),
                MemberTrack.id == sa.null(),
            )
        )

        results: List[ClientTrack] = query.all()

        return results

    def get_all_users_based_on_org_id(self, org_id: int) -> List[tuple]:
        """
        Get the user Ids from all the active member tracks attached to the provided organization ID
        """
        query: sqlalchemy.orm.Query = (
            self.session.query(MemberTrack.user_id)
            .outerjoin(
                ClientTrack,
                sa.and_(
                    MemberTrack.client_track_id == ClientTrack.id,
                    MemberTrack.active == sa.true(),
                ),
            )
            .filter(ClientTrack.organization_id == org_id)
        )

        result: List[tuple] = query.all()

        return result

    def has_active_wallet(self, track: ClientTrack) -> bool:
        """
        Check if organization has wallet or not with the client_track
        """
        org_settings = (
            self.session.query(ReimbursementOrganizationSettings)
            .filter_by(
                organization=track.organization,
            )
            .all()
        )
        active_settings = [s for s in org_settings if s.is_active]
        return True if active_settings else False
