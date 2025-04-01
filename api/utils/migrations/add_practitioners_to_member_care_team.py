from datetime import datetime

from appointments.models.appointment import Appointment
from authn.models.user import User
from care_advocates.models.assignable_advocates import AssignableAdvocate
from messaging.models.messaging import Channel, ChannelUsers
from models.profiles import CareTeamTypes, MemberPractitionerAssociation
from models.referrals import ReferralCodeUse, ReferralCodeValueTypes
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def create_care_team_for_all_active_users(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    user_ids=[],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
):
    now = datetime.utcnow().replace(microsecond=0)
    users = (
        User.query.filter(User.id.in_(user_ids)).all()
        or User.query.filter(User.active.is_(True)).all()
    )
    for user in users:
        existing_practitioner_ids = [pp.user_id for pp in user.care_team]
        try:
            appointments = Appointment.query.filter(
                Appointment.member_schedule_id == user.schedule.id
            ).all()
            appt_practitioner_ids = {a.practitioner.id for a in appointments}
            print("%s appointment practitioners" % len(appt_practitioner_ids))

            # care team via appointments
            for practitioner_id in appt_practitioner_ids:
                if practitioner_id in existing_practitioner_ids:
                    continue  # skip if care team association already exists
                user.practitioner_associations.append(
                    MemberPractitionerAssociation(
                        user_id=user.id,
                        practitioner_id=practitioner_id,
                        type=CareTeamTypes.APPOINTMENT,
                        json={"migrated_at": now.isoformat()},
                    )
                )
                log.info(
                    "Inserting rows in MemberPractitionerAssociation",
                    user_id=user.id,
                    practitioner_id=practitioner_id,
                )
                existing_practitioner_ids.append(practitioner_id)

            codes = ReferralCodeUse.free_practitioner_codes_for_member(user.id)
            code_practitioner_ids = {c.user.id for c in codes}
            print("%s free code practitioners" % len(code_practitioner_ids))

            # care team via free forever codes
            for practitioner_id in code_practitioner_ids:
                if practitioner_id in existing_practitioner_ids:
                    continue  # skip dupes
                user.practitioner_associations.append(
                    MemberPractitionerAssociation(
                        user_id=user.id,
                        practitioner_id=practitioner_id,
                        type=CareTeamTypes.FREE_FOREVER_CODE,
                        json={"migrated_at": now.isoformat()},
                    )
                )
                log.info(
                    "Inserting rows in MemberPractitionerAssociation",
                    user_id=user.id,
                    practitioner_id=practitioner_id,
                )
                existing_practitioner_ids.append(practitioner_id)

            channels = (
                db.session.query(Channel)
                .join(ChannelUsers)
                .filter(ChannelUsers.user_id == user.id)
                .all()
            )
            messaging_practitioners = set(
                [c.practitioner.id for c in channels if c.practitioner]
            )
            print("%s messaging practitioners" % len(messaging_practitioners))

            # care team via messages
            for practitioner_id in messaging_practitioners:
                if practitioner_id in existing_practitioner_ids:
                    continue  # skip if care team association is already exist
                user.practitioner_associations.append(
                    MemberPractitionerAssociation(
                        user_id=user.id,
                        practitioner_id=practitioner_id,
                        type=CareTeamTypes.MESSAGE,
                        json={"migrated_at": now.isoformat()},
                    )
                )
                log.info(
                    "Inserting rows in MemberPractitionerAssociation",
                    user_id=user.id,
                    practitioner_id=practitioner_id,
                )
                existing_practitioner_ids.append(practitioner_id)

            db.session.add(user)
            db.session.commit()

            print("User[%s] care team migrated" % user.id)
        except Exception as e:
            print("ERROR: %s. Please manually migrate %s" % (e, user))

    print("Total of %s users have been migrated." % len(users))


def create_care_team_for_users_with_usages():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    cs_practitioner_id = AssignableAdvocate.default_care_coordinator().id
    sql = """
(
    SELECT DISTINCT u.`id`
    FROM appointment a JOIN `schedule` s ON (a.member_schedule_id=s.id)
        JOIN `user` u ON (s.user_id=u.id)
) UNION (
    SELECT DISTINCT u.`id`
    FROM `channel_users` cu JOIN `member_profile` mp ON (cu.user_id=mp.user_id)
        JOIN `user` u ON (cu.user_id=u.id)
    WHERE cu.channel_id NOT IN (
        SELECT c.id
        FROM channel c JOIN channel_users cu_1 ON (c.id=cu_1.channel_id)
            JOIN practitioner_profile pp ON (cu_1.user_id=pp.user_id)
        WHERE pp.user_id = :cs_practitioner_id
    )
) UNION (
    SELECT DISTINCT u.`id`
    FROM referral_code_use rcu JOIN referral_code rc ON (rcu.code_id=rc.id)
        JOIN referral_code_value rcv ON (rcv.code_id=rc.id)
        JOIN `user` u ON (rcu.user_id=u.id)
    WHERE rcv.for_user_type = :code_type
)
    """
    results = db.session.execute(
        sql,
        {
            "cs_practitioner_id": cs_practitioner_id,
            "code_type": ReferralCodeValueTypes.free_forever,
        },
    )

    all_user_ids = [r[0] for r in results.fetchall()]

    print("Total of %s users have usages." % len(all_user_ids))
    create_care_team_for_all_active_users(user_ids=all_user_ids)
