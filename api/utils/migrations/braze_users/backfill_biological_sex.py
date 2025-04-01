import warnings

from sqlalchemy.orm import Load

from app import create_app
from authn.models.user import User
from models.enterprise import (
    Assessment,
    AssessmentLifecycle,
    NeedsAssessment,
    NeedsAssessmentTypes,
)
from storage.connection import db
from utils.query import paginate
from views.assessments import (  # type: ignore[attr-defined] # Module "views.assessments" has no attribute "HealthStatusMixin"
    HealthStatusMixin,
)


def backfill_biological_sex_for_all_users():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    braze_batch_size = 100

    warnings.warn(  # noqa  B028  TODO:  No explicit stacklevel keyword argument found. The warn method from the warnings module uses a stacklevel of 1 by default. This will only show a stack trace for the line on which the warn method is called. It is therefore recommended to use a stacklevel of 2 or greater to provide more information to the user.
        """#pod-care-management NeedsAssessment is no longer managed in Mono.
        Objects are queryable on the /api/hdc/v1 API.
        """,
        DeprecationWarning,
    )
    query = (
        db.session.query(NeedsAssessment)
        .join(Assessment, NeedsAssessment.assessment_id == Assessment.id)
        .join(AssessmentLifecycle, AssessmentLifecycle.id == Assessment.lifecycle_id)
        .join(User, NeedsAssessment.user_id == User.id)
        .options(
            Load(User).load_only(User.id, User.esp_id),  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
            Load(NeedsAssessment).load_only(  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
                NeedsAssessment.assessment_id, NeedsAssessment.json
            ),
            Load(Assessment).load_only(  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
                Assessment.id, Assessment.quiz_body, Assessment.lifecycle_id
            ),
            Load(AssessmentLifecycle).load_only(  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
                AssessmentLifecycle.id, AssessmentLifecycle.type
            ),
        )
        .filter(
            AssessmentLifecycle.type.in_(
                (
                    NeedsAssessmentTypes.PARTNER_PREGNANCY_ONBOARDING,
                    NeedsAssessmentTypes.PARTNER_NEWPARENT_ONBOARDING,
                    NeedsAssessmentTypes.PARTNER_FERTILITY_ONBOARDING,
                    NeedsAssessmentTypes.GENERAL_WELLNESS_ONBOARDING,
                    NeedsAssessmentTypes.ADOPTION_ONBOARDING,
                    NeedsAssessmentTypes.SURROGACY_ONBOARDING,
                    NeedsAssessmentTypes.PARENTING_AND_PEDIATRICS_ONBOARDING,
                )
            )
        )
    )

    for needs_assessments in paginate(
        query, NeedsAssessment.user_id, size=braze_batch_size, chunk=True
    ):
        for na in needs_assessments:
            HealthStatusMixin().apply_biological_sex(na.user, na)


if __name__ == "__main__":
    with create_app().app_context():
        backfill_biological_sex_for_all_users()
