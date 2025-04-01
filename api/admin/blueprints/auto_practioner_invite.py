import flask_login as login
from flask import Blueprint, abort, flash, redirect, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from admin.common import https_url
from appointments.models.cancellation_policy import (
    CancellationPolicy,
    CancellationPolicyName,
)
from authn.models.user import User
from authz.models.roles import ROLES
from health.domain.add_profile import add_profile_to_user
from models.referrals import (
    PractitionerInvite,
    ReferralCode,
    ReferralCodeValue,
    ReferralCodeValueTypes,
)
from payments.models.practitioner_contract import ContractType
from storage.connection import db
from utils.log import logger

URL_PREFIX = "auto_practitioner_invite"

log = logger(__name__)
auto_practitioner_invite = Blueprint(URL_PREFIX, __name__)


@auto_practitioner_invite.route("/send", methods=["POST"])
@login.login_required
def auto_send_practitioner_invite():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    email = request.form.get("email")
    referral_code = request.form.get("referral_code")

    if not email or not referral_code:
        abort(400)

    try:
        user = (
            db.session.query(User)
            .filter((func.lower(User.email) == email.lower()))
            .one()
        )
        if user.is_practitioner:
            err_msg = f"User: ({user.id}) already has a practitioner profile!"
            log.debug(err_msg)
            flash(err_msg, "error")
            return redirect("/auto_practitioner_invite")
        elif user.is_member:
            user = add_profile_to_user(user, ROLES.practitioner, **vars(user))
            profile = user.practitioner_profile
            profile.messaging_enabled = True
            cancellation_policy_name = CancellationPolicyName.default().value
            if profile.active_contract and profile.active_contract.contract_type in [
                ContractType.HYBRID_1_0,
                ContractType.HYBRID_2_0,
            ]:
                cancellation_policy_name = CancellationPolicyName.FLEXIBLE.value
            policy = (
                db.session.query(CancellationPolicy)
                .filter(CancellationPolicy.name == cancellation_policy_name)
                .first()
            )
            if policy:
                profile.default_cancellation_policy_id = policy.id
            db.session.add(profile)
            db.session.commit()
            log.debug(f"Practitioner profile added with User: ({profile.user_id})")

            code = ReferralCode(
                allowed_uses=None,
                user_id=user.id,
                expires_at=None,
                code=referral_code,
                only_use_before_booking=True,
            )
            ff_code_value = ReferralCodeValue(
                code=code, for_user_type=ReferralCodeValueTypes.free_forever
            )
            member_code_value = ReferralCodeValue(
                code=code, value=25, for_user_type=ReferralCodeValueTypes.member
            )
            db.session.add_all([code, ff_code_value, member_code_value])
            db.session.commit()
            log.debug(
                f"Free forever code {ff_code_value} and its member value {member_code_value} added",
            )
    except NoResultFound:
        #  Save an invite and stash code in it if one doesn't already exist
        exists = db.session.query(PractitionerInvite).filter_by(email=email).first()
        if not exists:
            invite = PractitionerInvite(
                email=email, image_id=194, json={"referral_code": referral_code}
            )
            db.session.add(invite)
            db.session.commit()
            log.debug(
                "User does not exist. PractitionerInvite: (%s) is added.", invite.id
            )
    except MultipleResultsFound as mrfe:
        log.debug("User table integrity error: %s", mrfe)
        abort(400)
    except IntegrityError as e:
        log.debug("IntegrityError reported: %s", e)
        abort(400)

    success_msg = f"Practitioner invite is set for {email}"
    flash(success_msg)
    return redirect(https_url("admin.index"))
