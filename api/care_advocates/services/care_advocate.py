from __future__ import annotations

import datetime
from typing import Dict, List, Optional

from ddtrace import tracer
from sqlalchemy.exc import IntegrityError

from appointments.utils.booking import (
    MassAvailabilityCalculator,
    PotentialPractitionerAvailabilities,
)
from authn.domain.service import UserService
from authn.models.user import User
from care_advocates.models.assignable_advocates import AssignableAdvocate
from care_advocates.repository.assignable_advocate import AssignableAdvocateRepository
from care_advocates.tasks.care_advocate import (
    check_care_advocates_for_3_day_availability,
)
from models.profiles import MemberProfile, PractitionerProfile
from models.tracks import MemberTrack
from models.verticals_and_specialties import CX_VERTICAL_NAME
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class CareAdvocateAlreadyAssigned(Exception):
    def __init__(self, selected_cx):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.selected_cx = selected_cx
        self.message = f"Care advocate {selected_cx} is already assigned to care team"


class CareAdvocateService:
    def keep_existing_ca_if_valid_and_member_transitioning_tracks(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, user_id: int, potential_new_cas_ids
    ):
        """

        Given a list of potential new CAs for a member, we will reduce the list to the member's
        existing CA if the member is transitioning to a new track and their existing CA
        is in the list of potential new CAs.
        """

        # TODO: We would like to stop querying the User sqlalchemy model, and rather use the
        # UserService. Nonetheless, given that we are relying on the .care_coordinators and .inactive_tracks
        # properties, until those get migrated to respective services, we have to rely on the User object
        user = db.session.query(User).get(user_id)

        # If user has no existing CA, return the same list of potential new CAs
        if not user.care_coordinators:
            return potential_new_cas_ids

        user_ca = user.care_coordinators[0]
        # If user's existing CA is not in list of potential new CAs, return the same list of potential new CAs
        if user_ca.id not in potential_new_cas_ids:
            return potential_new_cas_ids

        # If user is not transitioning tracks, return the same list of potential new CAs
        # A user can be said to be transitioning tracks if they have inactive tracks
        if not user.inactive_tracks:
            return potential_new_cas_ids

        # Else, return only the existing CA.
        # This applies for the case when the user's existing CA is in the list of potential new
        # CAs and the user is transitioning tracks. In this situation, its ideal for
        # the user to keep their existing Ca.
        log.info(
            "Will only keep existing CA given user is transitioning tracks",
            user_id=user.id,
            existing_ca=user_ca.id,
            inactive_tracks=str([t.name for t in user.inactive_tracks]),
        )
        return [user_ca.id]

    @tracer.wrap()
    def get_potential_care_coordinators_for_member(
        self,
        user_id: int,
        filter_by_language: Optional[str] = None,
        availability_before: datetime.datetime | None = None,
    ) -> list[int]:
        """
        @param filter_by_language: the iso-369-3/alpha-3 code for a language to filter
                                   practitioners by, or none
        """
        # TODO: Change query for UserService.get_user
        user: User = User.query.get(user_id)
        user_flags = user.current_risk_flags()

        # We want to collect  logs for later emission, so that our alerts can append
        # information about the CA who is eventually matched to this user at the end of the process.
        logs_to_emit_with_matched_ca = []

        log.info(
            "Checking potential care coordinators for member",
            user_id=user_id,
            user_flags=user_flags,
        )

        (
            assignable_advocates,
            all_available_advocate_ids,
        ) = AssignableAdvocate.find_potential_care_advocates(
            user,
            user_flags,
            filter_by_language=filter_by_language,
            availability_before=availability_before,
            logs_to_emit_with_matched_ca=logs_to_emit_with_matched_ca,
        )

        if not assignable_advocates:
            # DD monitor: https://app.datadoghq.com/monitors/126032680
            log.warn(
                "No potential care coordinators found for member - offering times for all available advocates",
                user_id=user_id,
                track=user.active_tracks,
                country=user.country and user.country.alpha_2,
                organization=user.organization,
                risk_factors=user_flags,
                filter_by_language=filter_by_language,
            )
            logs_to_emit_with_matched_ca.append(
                "No potential care coordinators found for member - offering times for all available advocates"
            )
            care_advocate_ids = all_available_advocate_ids
        else:
            care_advocate_ids = [aa.practitioner_id for aa in assignable_advocates]

        if not care_advocate_ids:
            log.warn(
                "No available CAs found in the next 7 days",
                user_id=user_id,
                track=user.active_tracks,
                country=user.country and user.country.alpha_2,
                organization=user.organization,
                risk_factors=user_flags,
            )
            logs_to_emit_with_matched_ca.append(
                "No available CAs found in the next 7 days"
            )

        # check to see if any CA's within the group have availability within the next 3 days
        check_care_advocates_for_3_day_availability.delay(
            care_advocate_ids, user_id, team_ns="care_discovery"
        )

        return care_advocate_ids

    @tracer.wrap()
    def _merge_availabilities(
        self, all_pracs_availabilities: List[PotentialPractitionerAvailabilities]
    ) -> Dict[datetime.datetime, List[int]]:
        """'
        Grab a list of practitioners availabilities and merged them into a dictionary where keys are availabilities start time and values are practitioners ids that are available in such timeslot

        Returns:
            dict[timeslot_start_time]=[<ca_id>]
        """
        availabilities_to_practitioners = {}

        # For each practitioner
        for prac_availability in all_pracs_availabilities:
            # Loop over their available timeslots
            for avail in prac_availability.availabilities:
                # Grab start time
                timeslot_start = avail.scheduled_start
                # Append prac id to list of pracs available in time slot
                availabilities_to_practitioners.setdefault(timeslot_start, []).append(
                    prac_availability.practitioner_id
                )

        log.info(
            "Merged practitioners availabilities",
            practititioners_ids=[pa.practitioner_id for pa in all_pracs_availabilities],
        )
        # make sure we return the times in order
        return dict(sorted(availabilities_to_practitioners.items()))

    @tracer.wrap()
    def _get_practitioners_availabilities(
        self,
        prac_profiles: List[PractitionerProfile],
        start_at: datetime.datetime,
        end_at: datetime.datetime,
    ) -> List[PotentialPractitionerAvailabilities]:
        availabilities = MassAvailabilityCalculator().get_practitioner_availabilities(
            practitioner_profiles=prac_profiles,
            start_time=start_at,
            end_time=end_at,
            limit=1000,  # TODO: define limit with FE
            offset=0,
            vertical_name=CX_VERTICAL_NAME,
        )
        return availabilities

    @tracer.wrap()
    def is_valid_list_cas_ids(self, ca_ids: List[int]) -> bool:
        # Note: In case this function is deemed too slow, we could run the list validation in the db like suggested here: https://gitlab.mvnapp.net/maven/maven/-/merge_requests/6641#note_298545

        if not ca_ids:
            return False

        all_existing_ca_ids = AssignableAdvocateRepository().get_all_aa_ids()

        missing_ca_ids = [id_ for id_ in ca_ids if id_ not in all_existing_ca_ids]
        return len(missing_ca_ids) == 0

    @tracer.wrap()
    def _log_time_coverage(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        n_pracs: int,
        start_at: datetime.datetime,
        end_at: datetime.datetime,
        covered_datetimes: List[datetime.datetime],
        user: User = None,  # type: ignore[assignment] # Incompatible default for argument "user" (default has type "None", argument has type "User")
    ):
        # Remove minutes, we just want to track coverage per hour
        covered_hours = [
            dt.replace(minute=0, second=0, microsecond=0) for dt in covered_datetimes
        ]

        # Remove duplicates
        covered_hours = set(covered_hours)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Set[datetime]", variable has type "List[datetime]")

        # Build a dict with all hours between start and end, and write a True for hours that have coverage
        coverage = {}

        hours_between_end_start = (
            int((end_at - start_at).total_seconds() / (60 * 60)) + 1
        )

        # Report starting from the hour following start_at, cause if start_at its at minute > 45, its probable that hour will not be covered
        for h in range(1, hours_between_end_start):
            datetime_to_report = start_at.replace(
                minute=0, second=0, microsecond=0
            ) + datetime.timedelta(hours=h)
            coverage[datetime_to_report.hour] = datetime_to_report in covered_hours

        fraction_of_hours_covered = round(
            len(covered_hours) / hours_between_end_start, 2
        )

        if user:
            user_id = user.id
            user_country_code = (
                db.session.query(MemberProfile.country_code)
                .filter_by(user_id=user_id)
                .first()
            )
            user_country_code = (
                user_country_code[0] if user_country_code else None
            )  # Given that db result is a tuple (value,)

            user_track = (
                db.session.query(MemberTrack.name)
                .filter(MemberTrack.user_id == user_id, MemberTrack.active == True)
                .order_by(MemberTrack.created_at.desc())
                .first()
            )
            user_track = user_track[0] if user_track else None

        else:
            user_country_code = None
            user_track = None
            user_id = None

        covered_datetimes_iso_format = [dt.isoformat() for dt in covered_datetimes]
        covered_hours_iso_format = [dt.isoformat() for dt in covered_hours]
        log.info(
            "Pooled availability coverage calculated!!!!",
            n_pracs=n_pracs,
            coverage=coverage,
            fraction_of_hours_covered=fraction_of_hours_covered,
            start_at=start_at.isoformat(),
            end_at=end_at.isoformat(),
            covered_datetimes=str(covered_datetimes_iso_format),
            covered_hours=str(covered_hours_iso_format),
            hours_between_end_start=hours_between_end_start,
            user_track=user_track,
            user_country_code=user_country_code,
            user_id=user_id,
        )

    @tracer.wrap()
    def build_pooled_availability(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        ca_ids: List[int],
        start_at: datetime.datetime,
        end_at: datetime.datetime,
        user=None,
    ) -> Dict[datetime.datetime, List[int]]:
        """
        For the given list of ca_ids, build a pooled calendar of their availability between start_at and end_at.
        user is an optional param user for logging.
        """

        log.info(
            "Starting to build pooled availability",
            ca_ids=ca_ids,
            start_at=start_at,
            end_at=end_at,
        )

        prac_profiles = (
            db.session.query(PractitionerProfile)
            .filter(PractitionerProfile.user_id.in_(ca_ids))
            .all()
        )

        availabilities = self._get_practitioners_availabilities(
            prac_profiles, start_at, end_at
        )

        merged_availabilities = self._merge_availabilities(availabilities)

        # Temporary logging time coverage
        n_pracs = len(prac_profiles)
        covered_datetimes = list(merged_availabilities.keys())
        self._log_time_coverage(n_pracs, start_at, end_at, covered_datetimes, user)

        return merged_availabilities

    @tracer.wrap()
    def is_valid_user_id(self, user_id: int) -> bool:
        return True if UserService().get_user(user_id=user_id) else False

    @tracer.wrap()
    def assign_care_advocate(self, user_id: int, ca_ids: List[int]) -> int:
        # TODO: Change query for UserService.get_user
        user = User.query.get(user_id)

        log.info(
            "Starting to assign care advocate",
            ca_ids=ca_ids,
            user_id=user_id,
        )

        current_ca_id = CareAdvocateService().check_list_for_current_care_advocate(
            ca_ids=ca_ids, user=user
        )
        if current_ca_id:
            log.info(
                "User already has a CA that meets matching criteria. Not reassigning CA",
                user_id=user_id,
                care_advocate_id=current_ca_id,
            )
            return current_ca_id

        AssignableAdvocate.remove_care_advocate_from_member(user)

        assignable_advocates = (
            AssignableAdvocateRepository().get_all_by_practitioner_ids(ids=ca_ids)
        )

        start_date = datetime.date.today()
        end_date = start_date + datetime.timedelta(days=6)
        selected_cx = AssignableAdvocate.get_cx_with_lowest_weekly_utilization(
            assignable_advocates, start_date, end_date, user_id
        )
        try:
            AssignableAdvocate.assign_selected_care_advocate(user, selected_cx)
            db.session.commit()
        except IntegrityError as e:
            if "Duplicate entry" in str(e):
                db.session.rollback()
                log.error(
                    "Duplicate entry error. Care advocate is already assigned to member's care team",
                    user_id=user_id,
                    practitioner_id=selected_cx.practitioner_id,
                    practitioner_associations=user.practitioner_associations,
                )
                raise CareAdvocateAlreadyAssigned(selected_cx.practitioner_id)

        log.info(
            "Care advocate successfully assigned",
            practitioner_id=selected_cx.practitioner_id,
            user_id=user_id,
        )

        return selected_cx.practitioner_id

    @tracer.wrap()
    def check_list_for_current_care_advocate(self, user: User, ca_ids: List[int]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not user.care_coordinators:
            return
        current_care_advocate = user.care_coordinators[0]
        if current_care_advocate.id in ca_ids:
            return current_care_advocate.id
        return

    @tracer.wrap()
    def limit_care_advocate_ids_by_next_availability(
        self, user_id: str | None, care_advocate_ids: list[int], limit: int = 20
    ) -> tuple[list[int], datetime.datetime | None]:
        """
        Returns the CAs with the nearest next_availability, and the soonest availability out of them
        """

        query_result = (
            db.session.query(
                PractitionerProfile.user_id, PractitionerProfile.next_availability
            )
            .filter(PractitionerProfile.user_id.in_(care_advocate_ids))
            .order_by(PractitionerProfile.next_availability)
            .limit(limit)
            .all()
        )
        if len(query_result):
            soonest_availability = query_result[0][1]
            log.info(
                "CAs found over the limit. Limited number of CAs.",
                limit=limit,
                care_advocate_ids=care_advocate_ids,
                user_id=user_id,
                num_care_advocates=len(care_advocate_ids),
            )
        else:
            soonest_availability = None

        return [ca_id[0] for ca_id in query_result], soonest_availability
