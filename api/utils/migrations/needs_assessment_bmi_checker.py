import warnings

from models.enterprise import NeedsAssessment
from storage.connection import db


def check_needs_assessment_answers_data():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    This is just run through the needs assessment answers data
    and print out abnormalities if encountered.
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

    results = db.session.execute(
        'SELECT id FROM needs_assessment WHERE json LIKE "%answers%"'
    )
    na_ids = [r[0] for r in results.fetchall()]

    nas = NeedsAssessment.query.filter(NeedsAssessment.id.in_(na_ids))
    for na in nas:
        answers = na.json.get("answers")
        if not answers:
            print("NeedsAssessment[%d] has empty or no answers" % na.id)
            continue
        if not isinstance(answers, list):
            print("NeedsAssessment[%d] has malformed answers. %s" % (na.id, answers))
            continue
        bmi_answers = [a for a in answers if a["id"] == 1]
        if not bmi_answers:
            print("NeedsAssessment[%d] has empty or no bmi answer(id=1)" % na.id)
            continue
        bmi_answer = bmi_answers[0]
        try:
            w = int(bmi_answer.get("weight") or 0)
            h = int(bmi_answer.get("height") or 0)
            assert isinstance(w, int) and isinstance(h, int)
        except Exception as e:
            print(e)
            continue

    print(f"Total needs assessments checked: {len(na_ids)}")
