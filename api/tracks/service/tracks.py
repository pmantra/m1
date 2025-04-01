from __future__ import annotations

from typing import DefaultDict, Dict, List, Optional

from maven import feature_flags

from common import stats
from eligibility.e9y import model as e9y_model
from eligibility.service import EnterpriseVerificationService, get_verification_service
from models.enterprise import Organization
from models.tracks import (
    ClientTrack,
    IncompatibleTrackError,
    InvalidOrganizationError,
    MemberTrack,
    MissingClientTrackError,
    MissingEmployeeError,
    TrackConfig,
    TrackName,
    get_track,
)
from storage.connection import db
from tracks import constants, repository
from utils import log

logger = log.logger(__name__)

__all__ = (
    "OrgIdToEligibleTracks",
    "TrackSelectionService",
    "MissingEnterpriseConfiguration",
)

OrgIdToEligibleTracks = Dict[int, List[TrackConfig]]


class TrackSelectionService:
    __slots__ = ("ver_svc", "tracks", "member_tracks")

    def __init__(self) -> None:
        self.ver_svc: EnterpriseVerificationService = get_verification_service()
        self.tracks: repository.TracksRepository = repository.TracksRepository()
        self.member_tracks: repository.MemberTrackRepository = (
            repository.MemberTrackRepository(session=db.session, is_in_uow=True)
        )

    def _get_enrollable_tracks(
        self,
        *,
        enrolled: List[MemberTrack],
        available: List[ClientTrack],
    ) -> List[ClientTrack]:
        """
        Given an org's e9y settings, a user's org-specific verification and their current enrollments,
        determine what tracks they are eligible to enroll in.

        This contains all of the business rules around track selection.
        """
        # Rule: When enrolled in 2 or more tracks, user can't enroll in more tracks
        if len(enrolled) >= 2:
            return []

        # Rule: When enrolled in 0 tracks, user can enroll in any track
        if not enrolled:
            return available

        # Rule: When enrolled in 1 non-pnp track, user can only enroll in pnp
        # Rule: When enrolled in pnp track, user can enroll in any other track
        if (
            len(enrolled) == 1
            and enrolled[0].name != TrackName.PARENTING_AND_PEDIATRICS
        ):
            available = [
                t for t in available if t.track == TrackName.PARENTING_AND_PEDIATRICS
            ]

        return available

    def get_organization_id_for_user(
        self,
        *,
        user_id: int,
    ) -> int | None:
        """
        Determine which organization a user belongs to, based their most recent active track. If
        no active tracks are found, it will return the organization ID of the most recent inactive
        track. The sorting of the tracks is handled by the get_all_enrolled_tracks function.

        We will need to update this when overeligibility allows users to register for multiple orgs
        """
        # TODO: Overeligibility- when a user can be enrolled in two orgs, will need to re-write this logic

        active_track_org_id = self.get_organization_id_for_user_via_active_tracks(
            user_id=user_id
        )
        if active_track_org_id:
            return active_track_org_id
        else:
            return self._get_organization_id_for_user_via_most_recent_track(
                user_id=user_id
            )

    def get_organization_id_for_user_via_active_tracks(
        self, *, user_id: int
    ) -> int | None:
        """
        get organization id via most recent active track.
        if no active track found, return None
        """
        enrolled_tracks = self.tracks.get_all_enrolled_tracks(
            user_id=user_id, active_only=True
        )
        # If we have at least one active track
        if enrolled_tracks:
            # Grab the unique orgs from these tracks to check for enrollment in multiple orgs
            org_ids = {track.organization.id for track in enrolled_tracks}
            if len(org_ids) > 1:
                logger.warn(
                    "Detected user enrolled in tracks for multiple organizations",
                    user_id=user_id,
                )
            return enrolled_tracks[0].organization.id
        else:
            return None

    def _get_organization_id_for_user_via_most_recent_track(
        self, *, user_id: int
    ) -> int | None:
        """
        get organization id via most recent track (including non-active tracks).
        if no tracks found, return None
        """
        enrolled_tracks = self.tracks.get_all_enrolled_tracks(
            user_id=user_id, active_only=False
        )

        if enrolled_tracks:
            return enrolled_tracks[0].organization.id
        else:
            return None

    def get_organization_for_user(
        self,
        *,
        user_id: int,
    ) -> Organization | None:
        """
        Determine which organization a user belongs to, based their most recent active track. If
        no active tracks are found, it will return the organization of the most recent inactive
        track. The sorting of the tracks is handled by the get_all_enrolled_tracks function.

        We will need to update this when overeligibility allows users to register for multiple orgs
        """
        # TODO: Overeligibility- when a user can be enrolled in two orgs, will need to re-write this logic
        org_id: int | None = self.get_organization_id_for_user(user_id=user_id)
        return Organization.query.get(org_id) if org_id is not None else None

    def get_enrollable_tracks_for_verification(
        self, *, verification: e9y_model.EligibilityVerification
    ) -> List[ClientTrack]:
        """
        Get a list of enrollable tracks based on org-specifc verification, computed based off of what the user
        is currently enrolled in and what is available.
        """
        enrolled: List[MemberTrack]
        available: List[ClientTrack]

        if verification is None:
            raise ValueError("Verification is needed for track enrollment")

        # Get the tracks that the user is currently enrolled in
        enrolled = self.member_tracks.get_active_tracks(user_id=verification.user_id)

        # Get the tracks that the user is eligible for, and not enrolled in
        available = self.tracks.get_available_tracks(
            user_id=verification.user_id, organization_id=verification.organization_id
        )

        return self._get_enrollable_tracks(
            enrolled=enrolled,
            available=available,
        )

    def get_enrollable_tracks_for_user_and_orgs(
        self, *, user_id: int, organization_ids: List[int]
    ) -> List[ClientTrack]:
        if not organization_ids:
            raise ValueError(
                "At least 1 organization id is needed for track enrollment"
            )

        # Get the tracks that the user is currently enrolled in
        enrolled: List[MemberTrack] = self.member_tracks.get_active_tracks(
            user_id=user_id
        )
        # Get the tracks that the user is eligible for, and not enrolled in
        all_available: List[ClientTrack] = self.tracks.get_all_available_tracks(
            user_id=user_id, organization_ids=organization_ids
        )

        available: List[ClientTrack] = self._apply_over_eligibility_rules(all_available)

        return self._get_enrollable_tracks(
            enrolled=enrolled,
            available=available,
        )

    def _apply_over_eligibility_rules(
        self, all_available: List[ClientTrack]
    ) -> List[ClientTrack]:
        """
        given list of all available track with multi organization,
        in case multiple orgs provides same track, pick up the right organization track based on
        overeligibility rules

        """
        if len(all_available) < 2:
            return all_available

        # track name -> tracks mapping, multiple orgs may provide same track
        name_to_tracks = DefaultDict(set)

        for track in all_available:
            name_to_tracks[track.track].add(track)

        available: List[ClientTrack] = []
        rule_funcs = [
            OverEligibilityRule.filter_by_wallet,
            OverEligibilityRule.filter_by_track_length,
            OverEligibilityRule.filter_by_number_of_active_tracks,
            OverEligibilityRule.filter_by_organization_id,
        ]
        for name in name_to_tracks:
            filtered = list(name_to_tracks[name])
            for func in rule_funcs:
                filtered = func(filtered)
            if len(filtered) == 1:
                available.append(filtered[0])
            else:
                input_client_track_ids = [t.id for t in list(name_to_tracks[name])]
                output_client_track_ids = [t.id for t in filtered]
                logger.error(
                    "0 or multiple tracks after overelgibility rules applied",
                    input_client_track_ids=input_client_track_ids,
                    output_client_track_ids=output_client_track_ids,
                )
                raise OverEligibilityRuleError(
                    input_client_track_ids=input_client_track_ids,
                    output_client_track_ids=output_client_track_ids,
                )
        return available

    def get_enrollable_tracks_for_org(
        self, *, user_id: int, organization_id: int
    ) -> List[ClientTrack]:
        """
        Get a list of ClientTracks for the user_id/organization_id combo that the user is currently able to enroll in,
        filtering out non-PnP tracks if the user already has non-PnP, and filtering out PnP if the user already has PnP.
        """
        verification: e9y_model.EligibilityVerification = (
            self.ver_svc.get_verification_for_user_and_org(
                user_id=user_id, organization_id=organization_id
            )
        )

        if not verification:
            logger.error(
                "Could not find a verification for this user_id and organization_id",
                user_id=user_id,
                organization_id=organization_id,
            )
            return []

        if not self.ver_svc.is_verification_active(verification=verification):
            logger.error(
                "Verification is no longer valid for this user and org",
                user_id=user_id,
                organization_id=organization_id,
            )
            return []

        if organization_id and verification.organization_id != organization_id:
            logger.error(
                "The user has an active verification but not at this org",
                user_id=user_id,
                organization_id=organization_id,
            )
            return []

        return self.get_enrollable_tracks_for_verification(verification=verification)

    def get_available_tracks_for_org(
        self, *, user_id: int, organization_id: int
    ) -> List[ClientTrack]:
        """
        Get a list of ClientTracks for the user_id/organization_id combo that are available to the user
        to add or transition to. This excludes active enrolled tracks, but does not filter for only tracks the
        user can add without leaving their current one like #get_enrollable_tracks_for_org does.
        """
        verification: e9y_model.EligibilityVerification = (
            self.ver_svc.get_verification_for_user_and_org(
                user_id=user_id, organization_id=organization_id
            )
        )

        if not verification:
            logger.error(
                "Could not find a verification for this user_id",
                user_id=user_id,
            )
            return []

        if organization_id and verification.organization_id != organization_id:
            logger.error(
                "The user has an active verification but not at this org",
                user_id=user_id,
                organization_id=organization_id,
            )
            return []

        # Get the tracks that the user is eligible for, and not enrolled in
        available = self.tracks.get_available_tracks(
            user_id=verification.user_id, organization_id=verification.organization_id
        )

        return available

    def validate_initiation(
        self,
        *,
        track: TrackName,
        user_id: int,
        organization_id: Optional[int] = None,
        should_bypass_eligibility: bool = False,
    ) -> ClientTrack:
        if organization_id is None:
            stats.increment(
                metric_name="overeligibility.tracks.validate_initiation.organization_id.missing",
                pod_name=stats.PodNames.ELIGIBILITY,
            )
            logger.error(
                "organization_id is missing for initialization.",
                user_id=user_id,
                track=track,
            )
            raise MissingEmployeeError(
                f"organization_id is required for initialization. user_id: {user_id}"
            )
        if not should_bypass_eligibility:
            verification = self.ver_svc.get_verification_for_user_and_org(
                user_id=user_id,
                active_verification_only=True,
                organization_id=organization_id,
            )
            if not verification:
                raise MissingEmployeeError(
                    f"No enterprise active verification was found for user_id: {user_id}"
                )
            organization = Organization.query.get(verification.organization_id)

            if not self.ver_svc.is_active(activated_at=organization.activated_at):
                raise InvalidOrganizationError(
                    f"Organization: {organization.id} is not active"
                )

        client_track: ClientTrack | None = self.tracks.get_client_track(
            organization_id=organization.id, track=track, active_only=True
        )
        if not client_track:
            raise MissingClientTrackError(
                f"Organization {organization.id} is not configured for track {track}"
            )

        if not should_bypass_eligibility:
            enrollable_tracks: List[ClientTrack] = self.get_enrollable_tracks_for_org(
                user_id=user_id, organization_id=organization.id
            )

            if track not in [t.track for t in enrollable_tracks]:
                raise IncompatibleTrackError(
                    f"Track {track} is not in the enrollable track list for user_id: {user_id}"
                    f" in organization_id: {organization.id}"
                )

        return client_track

    def is_enterprise(self, *, user_id: int) -> bool:
        """Determine if a user is an enterprise user based on if they are enrolled in a track"""
        return bool(self.member_tracks.get_active_tracks(user_id=user_id))

    @staticmethod
    def _get_ordered_recommended_tracks(
        previous_track: TrackName, enrollable_tracks: List[ClientTrack]
    ) -> List[TrackConfig]:
        if previous_track not in constants.ORDERED_TRACK_RECOMMENDATIONS:
            return [TrackConfig.from_name(t.name) for t in enrollable_tracks]

        ordered_track_names = constants.ORDERED_TRACK_RECOMMENDATIONS[previous_track]

        enrollable_tracks_for_previous_track = [
            t for t in enrollable_tracks if t.track in ordered_track_names
        ]

        sorted_client_tracks = sorted(
            enrollable_tracks_for_previous_track,
            key=lambda track: (
                ordered_track_names.index(track.name)
                if track.track in ordered_track_names
                else len(ordered_track_names)
            ),
        )

        return [TrackConfig.from_name(t.name) for t in sorted_client_tracks]

    def get_ordered_recommended_tracks(
        self, *, user_id: int, organization_id: int, previous_track: TrackName
    ) -> List[TrackConfig]:
        enrollable_tracks = self.get_enrollable_tracks_for_org(
            user_id=user_id, organization_id=organization_id
        )

        return self._get_ordered_recommended_tracks(
            previous_track=previous_track, enrollable_tracks=enrollable_tracks
        )

    def get_updated_track_description(
        self,
        *,
        user_id: int,
        organization_id: int,
        track_description: str,
        track_name: str,
    ) -> str:
        """Return a track description customized for the member"""
        if track_name in (TrackName.POSTPARTUM, TrackName.PARTNER_NEWPARENT):
            length = self._get_track_length(
                organization_id=organization_id, track_name=track_name
            )
            if not length:
                return track_description

            track = TrackConfig.from_name(TrackName(track_name))

            if str(length) in track.descriptions_by_length_in_days:
                return track.descriptions_by_length_in_days[str(length)]

        return track_description

    def _get_track_length(
        self, *, organization_id: int, track_name: str
    ) -> Optional[int]:
        client_track = self.tracks.get_client_track(
            organization_id=organization_id, track=track_name
        )
        return None if client_track is None else client_track.length_in_days

    def _is_eligible_for_intro_appointment(self, *, track_name: str) -> bool:
        eligible_tracks = feature_flags.str_variation(
            "eligible-tracks-for-ca-intro-appointment",
            default="",
        )
        logger.info(f"eligible_tracks is {eligible_tracks}")
        return track_name in eligible_tracks.split(", ")

    def any_eligible_for_intro_appointment(self, *, track_names: list[str]) -> bool:
        return any(
            self._is_eligible_for_intro_appointment(track_name=track_name)
            for track_name in track_names
        )

    def get_highest_priority_track(
        self, tracks: list[MemberTrack]
    ) -> MemberTrack | None:
        if not tracks:
            return None
        tracks.sort(key=lambda x: get_track(x.name).priority, reverse=True)
        return tracks[0]

    def get_users_by_org_id(self, org_id: int) -> List[tuple]:
        return self.tracks.get_all_users_based_on_org_id(org_id=org_id)


class MissingEnterpriseConfiguration(Exception):
    pass


class OverEligibilityRuleError(Exception):
    """
    OverEligibility Rules output 0 or multiple tracks

    :param input_client_track_ids: id list of input client tracks.
    :param output_client_track_ids: id list of output client tracks.
    """

    def __init__(
        self, input_client_track_ids: List[int], output_client_track_ids: List[int]
    ) -> None:
        self.input_client_track_ids = input_client_track_ids
        self.output_client_track_ids = output_client_track_ids

    def __str__(self) -> str:
        return f"0 or multiple tracks after rules input: {self.input_client_track_ids}, output: {self.output_client_track_ids}"


class OverEligibilityRule:
    @staticmethod
    def has_active_wallet(track: ClientTrack) -> bool:
        repo: repository.TracksRepository = repository.TracksRepository()
        return repo.has_active_wallet(track)

    @staticmethod
    def get_number_of_active_tracks(track: ClientTrack) -> int:
        repo: repository.TracksRepository = repository.TracksRepository()
        active_tracks = repo.get_active_tracks(organization_id=track.organization_id)
        return len(active_tracks)

    @staticmethod
    def filter_by_wallet(client_tracks: List[ClientTrack]) -> List[ClientTrack]:
        if len(client_tracks) <= 1:
            return client_tracks
        with_wallet = []
        for track in client_tracks:
            if OverEligibilityRule.has_active_wallet(track=track):
                with_wallet.append(track)
        return with_wallet if with_wallet else client_tracks

    @staticmethod
    def filter_by_track_length(client_tracks: List[ClientTrack]) -> List[ClientTrack]:
        if len(client_tracks) <= 1:
            return client_tracks
        max_track_length = -1
        res = []
        for track in client_tracks:
            track_length = 0 if track.length_in_days is None else track.length_in_days
            if track_length > max_track_length:
                max_track_length = track_length
                res = [track]
            elif track_length == max_track_length:
                res.append(track)
        return res

    @staticmethod
    def filter_by_number_of_active_tracks(
        client_tracks: List[ClientTrack],
    ) -> List[ClientTrack]:
        if len(client_tracks) <= 1:
            return client_tracks

        max_number_of_active_tracks = -1
        res = []
        for track in client_tracks:
            number_of_active_tracks = OverEligibilityRule.get_number_of_active_tracks(
                track
            )
            if number_of_active_tracks > max_number_of_active_tracks:
                max_number_of_active_tracks = number_of_active_tracks
                res = [track]
            elif number_of_active_tracks == max_number_of_active_tracks:
                res.append(track)
        return res

    @staticmethod
    def filter_by_organization_id(
        client_tracks: List[ClientTrack],
    ) -> List[ClientTrack]:
        if len(client_tracks) <= 1:
            return client_tracks

        with_max_organization_id = max(
            client_tracks, key=lambda track: track.organization_id
        )

        return [with_max_organization_id]
