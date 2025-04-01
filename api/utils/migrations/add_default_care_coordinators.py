from datetime import datetime

from care_advocates.models.assignable_advocates import AssignableAdvocate
from models.profiles import CareTeamTypes, MemberPractitionerAssociation
from storage.connection import db


def add_default_care_coordinator_for_existing_members():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    default_coordinator = AssignableAdvocate.default_care_coordinator()
    if not default_coordinator:
        print("No default care coordinator detected. Exiting.")
        return

    print("Default care coordinator is %s" % default_coordinator)
    sql = """SELECT u.id FROM `user` u
             JOIN member_profile mp ON (u.id = mp.user_id)
             LEFT JOIN practitioner_profile pp ON (u.id = pp.user_id)
             LEFT JOIN member_care_team mct ON (u.id = mct.user_id AND mct.type = :cc_type AND mct.practitioner_id = :pid)
             WHERE pp.user_id IS NULL AND mct.user_id IS NULL"""

    results = db.session.execute(
        sql,
        {
            "cc_type": CareTeamTypes.CARE_COORDINATOR.value,
            "pid": default_coordinator.id,
        },
    )

    member_ids = [r[0] for r in results.fetchall()]
    print(
        "Total %s members to be migrated with default care coordinator"
        % len(member_ids)
    )

    now = datetime.utcnow().replace(microsecond=0).isoformat()
    for member_id in member_ids:
        db.session.add(
            MemberPractitionerAssociation(
                user_id=member_id,
                type=CareTeamTypes.CARE_COORDINATOR.value,
                practitioner_id=default_coordinator.id,
                json={"migrated_at": now},
            )
        )
        db.session.commit()
        print("Added default coordinator for User<%s>" % member_id)

    print("Done!")
