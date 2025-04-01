from __future__ import annotations

from typing import List, Set

import ddtrace
from flask import request

from authn.models.user import User
from common.services.api import AuthenticatedResource
from eligibility import service, web
from eligibility.e9y import model as e9y_models
from eligibility.utils.verification_utils import is_over_eligibility_enabled
from models.enterprise import Organization
from storage.connection import db
from tracks.service import TrackSelectionService
from tracks.service.feature import build_tracks_data
from views.schemas.common import format_json_as_error


class FeaturesResource(AuthenticatedResource):
    def __init__(self) -> None:
        self.verification_service = service.EnterpriseVerificationService()

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        with web.handle_verification_errors():
            # Try looking up the current association for a user first.
            if is_over_eligibility_enabled():
                verification_list = web.verify_members(
                    user_id=self.user.id,
                    client_params=request.args,
                    svc=self.verification_service,
                )

                verifications = verification_list
                return _features_v2(user=self.user, verifications=verifications)

            else:
                verification = web.verify_member(
                    user_id=self.user.id,
                    client_params=request.args,
                    svc=self.verification_service,
                )
                return _features(user=self.user, verification=verification)


@ddtrace.tracer.wrap()
def get_pending_organization_agreements(user: User, organization_ids: Set[int]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Get a list of info about the pending agreements for the User that are specific to that User's organization.
    An agreement is pending if we do not have a corresponding AgreementAcceptance.
    @return: list of dictionaries containing the name, display_name, and version of the agreement
    """
    return [
        {
            "name": pending_agreement.name.value,  # type: ignore[union-attr] # Item "str" of "Optional[str]" has no attribute "value" #type: ignore[union-attr] # Item "None" of "Optional[str]" has no attribute "value"
            "display_name": pending_agreement.display_name,
            "version": pending_agreement.version,
            "optional": pending_agreement.optional,
        }
        for pending_agreement in user.get_pending_organization_agreements(
            organization_ids
        )
    ]


@ddtrace.tracer.wrap()
def get_pending_user_agreements(user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Get a list of info about the pending agreements for the User that are not specific to that User's organization.
    An agreement is pending if we do not have a corresponding AgreementAcceptance.
    @return: list of dictionaries containing the name, display_name, and version of the agreement
    """
    return [
        {
            "name": pending_agreement.name.value,  # type: ignore[union-attr] # Item "str" of "Optional[str]" has no attribute "value" #type: ignore[union-attr] # Item "None" of "Optional[str]" has no attribute "value"
            "display_name": pending_agreement.display_name,
            "version": pending_agreement.version,
            "optional": pending_agreement.optional,
        }
        for pending_agreement in user.pending_user_agreements
    ]


def get_all_pending_agreements(user: User, organization_ids: Set[int]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Get a list of info about the pending agreements for the User,
    including those that are specific to that User's organization.
    An agreement is pending if we do not have a corresponding AgreementAcceptance.
    @return: the name, display_name, and version of the agreements
    organized into Organization- and User-specific categories
    """
    return {
        "organization": get_pending_organization_agreements(user, organization_ids),
        "user": get_pending_user_agreements(user),
    }


def _features(user, verification: e9y_models.EligibilityVerification):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    track_service: TrackSelectionService = TrackSelectionService()

    available_tracks = track_service.get_enrollable_tracks_for_verification(
        verification=verification
    )

    if not available_tracks:
        return _no_available_tracks()

    organization = db.session.query(Organization).get(verification.organization_id)

    tracks_data = build_tracks_data(client_tracks=available_tracks)

    return (
        {
            "data": {
                "verified_employee": {
                    "organization_display_name": organization.marketing_name,
                    "all_pending_agreements": get_all_pending_agreements(
                        user=user, organization_ids={verification.organization_id}
                    ),
                },
                "modules": {
                    "eligible": tracks_data,
                },
            },
            "errors": [],
        },
        200,
    )


def _features_v2(user: User, verifications: List[e9y_models.EligibilityVerification]):  # type: ignore[no-untyped-def]
    """
    Determines the eligibility of the user across all organizations and returns the corresponding tracks.

    This method replaces the previous `_features` method. It checks all organizations the user may be eligible for and
    returns a set of corresponding tracks. If the user is eligible for the same track across multiple organizations,
    logic is applied to evaluate the priority of the track based on below criteria.
    1. has active wallet: track's organization has active wallet take the priority
    2. track length: track has longer length take the priority
    3. number of active tracks: track's organization has more active tracks take the priority
    4. organization created at: track's organization create later takes the priority


    Args:
    user: The user object for whom eligibility is being checked.
    verifications List[e9y_models.EligibilityVerification]: All verification objects containing the user's eligibility details.

    Returns:
    tuple: dictionary containing all track info and errors, along with a status code (200).
    """

    if not verifications:
        return _no_available_tracks()

    track_service: TrackSelectionService = TrackSelectionService()
    organization_ids = list(
        set([verification.organization_id for verification in verifications])
    )

    available_tracks = track_service.get_enrollable_tracks_for_user_and_orgs(
        user_id=user.id,
        organization_ids=organization_ids,
    )

    if not available_tracks:
        return _no_available_tracks()

    organizations = (
        db.session.query(Organization)
        .filter(Organization.id.in_(organization_ids))
        .all()
    )
    organization = organizations[0]

    tracks_data = build_tracks_data(client_tracks=available_tracks)

    return (
        {
            "data": {
                "verified_employee": {
                    "organization_display_name": organization.marketing_name,
                    "organizations": [
                        {
                            "id": org.id,
                            "marketing_name": org.marketing_name,
                        }
                        for org in organizations
                    ],
                    "all_pending_agreements": get_all_pending_agreements(
                        user=user, organization_ids={organization.id}
                    ),
                },
                "modules": {
                    "eligible": tracks_data,
                },
            },
            "errors": [],
        },
        200,
    )


def _no_available_tracks():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # TODO: do we need this error? Keeping it here for now to preserve behavior for
    #  existing enterprise users
    status = 409
    code = "NO_AVAILABLE_TRACKS"
    message = "Member is not eligible to enroll in any tracks at this time."
    return format_json_as_error(status, code, message)
