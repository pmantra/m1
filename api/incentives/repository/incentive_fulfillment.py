from __future__ import annotations

import datetime

import ddtrace

from authn.models.user import User
from incentives.models.incentive import IncentiveAction
from incentives.models.incentive_fulfillment import (
    IncentiveFulfillment,
    IncentiveStatus,
)
from models.tracks import MemberTrack, TrackName
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class IncentiveFulfillmentRepository:
    @ddtrace.tracer.wrap()
    def create(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        incentive_id,
        member_track_id,
        incentivized_action,
        date_status_changed,
        status,
    ):
        if status == IncentiveStatus.SEEN:
            incentive_fulfillment = IncentiveFulfillment(
                incentive_id=incentive_id,
                member_track_id=member_track_id,
                incentivized_action=incentivized_action,
                date_seen=date_status_changed,
                status=status,
            )
        # This elif statement should be removed once KICK-1598, given that then there will be no need to create
        # incentive_fulfillment rows with status EARNED from scratch
        elif status == IncentiveStatus.EARNED:
            incentive_fulfillment = IncentiveFulfillment(
                incentive_id=incentive_id,
                member_track_id=member_track_id,
                incentivized_action=incentivized_action,
                date_seen=date_status_changed,  # We are writing same date on date_seen just because we were not able to pick that exact moment before.
                date_earned=date_status_changed,
                status=status,
            )
        else:
            log.warning("Invalid status", status=status)
            return
        db.session.add(incentive_fulfillment)
        return incentive_fulfillment

    @ddtrace.tracer.wrap()
    def get_by_params(self, member_track_id, incentivized_action):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        incentive_fulfillment = (
            db.session.query(IncentiveFulfillment)
            .filter(
                IncentiveFulfillment.member_track_id == member_track_id,
                IncentiveFulfillment.incentivized_action == incentivized_action,
            )
            .first()
        )

        return incentive_fulfillment

    @ddtrace.tracer.wrap()
    def set_status(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        incentive_fulfillment: IncentiveFulfillment,
        status: IncentiveStatus,
        date_status_changed: datetime.datetime,
    ):
        if not incentive_fulfillment or not status:
            return

        incentive_fulfillment.status = status  # type: ignore[assignment] # Incompatible types in assignment (expression has type "IncentiveStatus", variable has type "str")

        # Update date_seen, date_earned or date_fulfilled
        if status == IncentiveStatus.SEEN:
            incentive_fulfillment.date_seen = date_status_changed
        elif status == IncentiveStatus.EARNED:
            incentive_fulfillment.date_earned = date_status_changed
        elif status == IncentiveStatus.FULFILLED:
            incentive_fulfillment.date_issued = date_status_changed

        db.session.add(incentive_fulfillment)

    @ddtrace.tracer.wrap()
    def get_all_by_ids(self, ids: list[int]) -> list[IncentiveFulfillment]:
        return (
            db.session.query(IncentiveFulfillment)
            .filter(IncentiveFulfillment.id.in_(ids))
            .all()
        )

    def get_all_by_params(self, track: TrackName, action: IncentiveAction):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Used for deleting incentive fulfillments in a script
        """
        return (
            db.session.query(IncentiveFulfillment, User.esp_id)
            .join(MemberTrack, MemberTrack.id == IncentiveFulfillment.member_track_id)
            .join(User, User.id == MemberTrack.user_id)
            .filter(
                IncentiveFulfillment.incentivized_action == action,
                MemberTrack.name == track,
            )
            .all()
        )
