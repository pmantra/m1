from models.enterprise import Assessment, AssessmentLifecycle
from storage.connection import db

from .sorting import sorted_by


@sorted_by("name")
def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        dict(
            name=l.name,
            type=l.type.value,
            versions=[
                dict(
                    version=a.version,
                    title=a.title,
                    description=a.description,
                    icon=a.icon,
                    slug=a.slug,
                    estimated_time=a.estimated_time,
                    quiz_body=a.quiz_body,
                    score_band=a.score_band,
                    json=a.json,
                )
                for a in l.assessments
            ],
            tracks=[t.value for t in l.allowed_track_names],
        )
        for l in AssessmentLifecycle.query
    ]


def restore(ll):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    assessments_by_lifecycle_name = {l["name"]: l["versions"] for l in ll}
    db.session.bulk_insert_mappings(AssessmentLifecycle, ll)
    lifecycle_id_by_name = {
        al.name: al.id
        for al in db.session.query(
            AssessmentLifecycle.name, AssessmentLifecycle.id
        ).all()
    }
    assessments = []
    for name, assessments_ in assessments_by_lifecycle_name.items():
        if assessments_:
            al_id = lifecycle_id_by_name[name]
            assessments.extend(
                (a.update(lifecycle_id=al_id) or a for a in assessments_)
            )
    db.session.bulk_insert_mappings(Assessment, assessments)
