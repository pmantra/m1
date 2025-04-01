import warnings
from typing import List

from authn.models.user import User
from models.enterprise import (
    Assessment,
    AssessmentLifecycle,
    AssessmentLifecycleTrack,
    NeedsAssessment,
)


def get_latest_track_assessments_for_user(user: User) -> List[Assessment]:
    """
    Returns a list of the most recent version of track assessments for a user based on their tracks
    """
    # Get tracks
    track_names = [track.name for track in user.member_tracks]

    # Get assessments via AssessmentLC via Allowed Tracks filter on tracks

    track_alcs = (
        AssessmentLifecycle.query.join(AssessmentLifecycle.allowed_tracks)
        .filter(AssessmentLifecycleTrack.track_name.in_(track_names))
        .all()
    )

    latest_track_assessments = [
        track_alcs.latest_assessment for track_alcs in track_alcs
    ]

    return latest_track_assessments


def get_user_track_and_started_needs_assessments(
    user: User,
) -> (List[NeedsAssessment], List[Assessment]):  # type: ignore[syntax] # Syntax error in type annotation
    """
    Gets all user needs assessments that have been started regardless if they have been finished or not along with all
    the assessments for the user's track whether the track assessments have been started or not. If a user has started
    or completed an assessment that assessment will be shown even if there is a more up to date assessment
    """
    warnings.warn(  # noqa  B028  TODO:  No explicit stacklevel keyword argument found. The warn method from the warnings module uses a stacklevel of 1 by default. This will only show a stack trace for the line on which the warn method is called. It is therefore recommended to use a stacklevel of 2 or greater to provide more information to the user.
        """#pod-care-management NeedsAssessment is no longer managed in Mono.
        This routine may be obsoleted and managed in HDC.

        Try:
            X-Maven-User-ID={user_id}
            GET /api/hdc/v1/assessments/{slug}/user-assessments/answers
        """,
        DeprecationWarning,
    )

    started_needs_assessments = NeedsAssessment.query.filter(
        NeedsAssessment.user == user
    ).all()
    track_assessments = get_latest_track_assessments_for_user(user)
    track_assessment_types = set(ta.lifecycle.type for ta in track_assessments)

    # Replace most recent
    for na in started_needs_assessments:
        na_type = na.assessment_template.lifecycle.type
        if na_type in track_assessment_types:
            track_assessment_types.remove(na_type)

    return_track_assessments = [
        ta for ta in track_assessments if ta.lifecycle.type in track_assessment_types
    ]

    return started_needs_assessments, return_track_assessments
