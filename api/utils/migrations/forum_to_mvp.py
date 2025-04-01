from appointments.models.payments import new_stripe_customer
from appointments.models.schedule import add_schedule_for_user
from authn.models.user import User
from authz.models.roles import ROLES, Role
from health.models.health_profile import HealthProfile
from models.products import add_products
from models.profiles import MemberProfile, PractitionerProfile
from models.referrals import ReferralCode, add_referral_code_for_user
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def migrate_practitioners():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    all_practitioners = db.session.query(PractitionerProfile).all()

    log.debug("Got %s to migrate", len(all_practitioners))
    for profile in all_practitioners:
        db.session.add(profile)
        db.session.commit()

        add_products(profile.user)

        if not profile.user.schedule:
            add_schedule_for_user(profile.user)

        log.debug("Migrated %s", profile.user)


def migrate_members():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    all_members = (
        db.session.query(User)
        .join(MemberProfile)
        .join(Role)
        .filter(Role.name == ROLES.member)
        .all()
    )

    log.debug("Got %s to migrate", len(all_members))
    for user in all_members:
        profile = user.member_profile
        if not profile.stripe_customer_id:
            profile.stripe_customer_id = new_stripe_customer(user)
            db.session.add(profile)

        if not HealthProfile.query.filter_by(user_id=user.id).first():
            h = HealthProfile(user=user)
            db.session.add(h)

        codes = (
            db.session.query(ReferralCode).filter(ReferralCode.user_id == user.id).all()
        )
        if not codes:
            add_referral_code_for_user(user.id)

        if not user.schedule:
            add_schedule_for_user(user)

        db.session.commit()
        log.debug("Migrated %s", user)
