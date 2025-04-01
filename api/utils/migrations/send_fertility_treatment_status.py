import warnings

from app import create_app
from models.enterprise import (
    Assessment,
    AssessmentLifecycle,
    NeedsAssessment,
    NeedsAssessmentTypes,
)
from storage.connection import db
from utils.log import logger
from views.assessments import (  # type: ignore[attr-defined] # Module "views.assessments" has no attribute "HealthStatusMixin"
    HealthStatusMixin,
)

log = logger(__name__)


def send_and_store_fertility_treatment_status():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    warnings.warn(  # noqa  B028  TODO:  No explicit stacklevel keyword argument found. The warn method from the warnings module uses a stacklevel of 1 by default. This will only show a stack trace for the line on which the warn method is called. It is therefore recommended to use a stacklevel of 2 or greater to provide more information to the user.
        """#pod-care-management Assessment & NeedsAssessment are no longer managed in Mono.
        This routine may be obsoleted and managed by new APIs in HDC.
        """,
        DeprecationWarning,
    )
    try:
        assessment_id = (
            db.session.query(Assessment)
            .join(AssessmentLifecycle)
            .filter(
                AssessmentLifecycle.type == NeedsAssessmentTypes.FERTILITY_ONBOARDING
            )
            .order_by(AssessmentLifecycle.id.desc())
            .first()
            .id
        )
    except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
        log.info("There was an error retrieving the assessment_id")

    try:
        user_assessments = (
            db.session.query(NeedsAssessment)
            .filter(NeedsAssessment.assessment_id == assessment_id)
            .all()
        )
    except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
        log.info("There was an error retrieving needs assessment data")

    for user_assessment in user_assessments:
        try:
            HealthStatusMixin.apply_fertility_treatment_status(user_assessment)
            db.session.add(user_assessment)
        except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
            log.info(
                f"There was an error migrating fertility treatment status for user esp_id {user_assessment.user.esp_id}"
            )

    db.session.commit()
    log.info("Fertility treatment status migration complete")


if __name__ == "__main__":
    with create_app().app_context():
        send_and_store_fertility_treatment_status()
