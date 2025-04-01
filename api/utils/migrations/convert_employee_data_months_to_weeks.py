from models.enterprise import OrganizationEmployee
from storage.connection import db


def convert_months_to_weeks():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    i = 0
    employees = OrganizationEmployee.query.all()
    for employee in employees:
        j = employee.json
        if j.get("initial_phase") and "month-" in j["initial_phase"]:
            j["old_initial_phase"] = j["initial_phase"]
            week_notation = "week-%s" % (
                4 * int(j["initial_phase"].replace("month-", ""))
            )
            j["initial_phase"] = week_notation
            db.session.add(employee)
            db.session.commit()
            print("Initial phase converted for %s" % employee)
            i += 1

    print("Total %s org employees have been converted." % i)
