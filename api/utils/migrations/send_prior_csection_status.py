import warnings

from sqlalchemy.orm import Load

from authn.models.user import User
from health.models.health_profile import HealthProfile
from models.enterprise import Assessment, NeedsAssessment
from models.tracks import MemberTrack
from storage.connection import db
from utils.log import logger
from views.assessments import (  # type: ignore[attr-defined] # Module "views.assessments" has no attribute "HealthStatusMixin"
    HealthStatusMixin,
)

log = logger(__name__)


def send_and_store_prior_c_section_status(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    assessment_ids=[],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
):
    for a_id in assessment_ids:
        send_and_store_prior_c_section_status_for_assessment(a_id)

    db.session.commit()
    log.info("Prior c-section status migration complete")


def send_and_store_prior_c_section_status_for_assessment(assessment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    warnings.warn(  # noqa  B028  TODO:  No explicit stacklevel keyword argument found. The warn method from the warnings module uses a stacklevel of 1 by default. This will only show a stack trace for the line on which the warn method is called. It is therefore recommended to use a stacklevel of 2 or greater to provide more information to the user.
        """#pod-care-management NeedsAssessment is no longer managed in Mono.
        Objects are queryable on the /api/hdc/v1 API.
        """,
        DeprecationWarning,
    )
    try:
        log.info("Retrieving needs assessments 😱", assessment_id=assessment_id)
        user_assessments = (
            db.session.query(NeedsAssessment)
            .join(User, User.id == NeedsAssessment.user_id)
            .join(HealthProfile, HealthProfile.user_id == User.id)
            .join(MemberTrack, MemberTrack.user_id == User.id)
            .options(
                Load(User).load_only(User.id),  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
                Load(NeedsAssessment).load_only(  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
                    NeedsAssessment.assessment_id, NeedsAssessment.json
                ),
                Load(Assessment).load_only(Assessment.quiz_body),  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
                Load(HealthProfile).load_only(HealthProfile.json),  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
                Load(MemberTrack).load_only(MemberTrack.ended_at),  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
            )
            .filter(
                NeedsAssessment.assessment_id == assessment_id,
                MemberTrack.ended_at == None,
            )
            .all()
        )
    except Exception as e:
        log.info(
            "Error retrieving needs assessment data",
            error=e,
            assessment_id=assessment_id,
        )

    for user_assessment in user_assessments:
        try:
            HealthStatusMixin().apply_prior_c_section_status(
                user_assessment.user, user_assessment
            )
            db.session.add(user_assessment)
        except Exception as e:
            log.info(
                f"Error migrating prior c-section status for user esp_id {user_assessment.user.esp_id}",
                error=e,
                assessment_id=assessment_id,
            )
