from models.enterprise import OrganizationEmployee
from tasks.marketing import (  # type: ignore[attr-defined] # Module "tasks.marketing" has no attribute "_tag_enterprise_user_organization"
    _tag_enterprise_user_organization,
)


def tag_org_for_existing_ent_users():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    employees = OrganizationEmployee.query.filter(
        OrganizationEmployee.json.contains("%claimed_by%")
    ).all()

    print("Got %s existing enterprise users." % len(employees))
    for employee in employees:
        if employee.user.is_enterprise:
            print("Tagging org %s for %s" % (employee.organization, employee.user))
            _tag_enterprise_user_organization(employee.user)
        else:
            print(
                "%s does not have active credit allocated. " "Skipping." % employee.user
            )
