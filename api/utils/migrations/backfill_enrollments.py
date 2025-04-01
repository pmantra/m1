from models.programs import CareProgram, Enrollment
from storage.connection import db


def backfill_enrollments():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    pp = db.session.query(CareProgram).all()
    pp_without_enrollment = [p for p in pp if not p.enrollment]
    print(
        "Backfilling enrollments for {}/{} care programs.".format(
            len(pp_without_enrollment), len(pp)
        )
    )
    for p in pp_without_enrollment:
        e = Enrollment(organization=p.organization_employee.organization)
        db.session.add(e)
        p.enrollment = e
        db.session.commit()
