import uuid
from datetime import date

import ddtrace
from sqlalchemy.orm import load_only
from sqlalchemy.sql import exists

import messaging.services.zendesk
from appointments.models.appointment import Appointment
from appointments.models.payments import Credit, PaymentAccountingEntry
from appointments.models.practitioner_appointment import PractitionerAppointmentAck
from appointments.models.schedule import Schedule
from authn.domain.service import authn
from authn.models.user import User
from braze import client
from care_advocates.models.assignable_advocates import AssignableAdvocate
from common.services.stripe import StripeConnectClient, StripeCustomerClient
from common.services.stripe_constants import PAYMENTS_STRIPE_API_KEY
from health.models.health_profile import HealthProfile
from messaging.models.messaging import (
    Channel,
    ChannelUsers,
    Message,
    MessageBilling,
    MessageCredit,
    MessageUsers,
)
from models.advertising import UserInstallAttribution
from models.enterprise import NeedsAssessment, UserOnboardingState
from models.forum import Post
from models.gdpr import GDPRRequestStatus, GDPRUserRequest
from models.profiles import (
    Address,
    AgreementAcceptance,
    Device,
    MemberPractitionerAssociation,
    MemberProfile,
)
from models.programs import CareProgram
from models.referrals import IncentivePayment, ReferralCode, ReferralCodeUse
from models.tracks import MemberTrack
from preferences.repository.member_preference import MemberPreferencesRepository
from storage.connection import db
from utils import sms
from utils.exceptions import DeleteUserActionableError
from utils.gdpr_backup_data import GDPRDataDelete
from utils.gdpr_deletion import GDPRDeleteUser
from utils.log import logger
from utils.mailchimp import unsubscribe_user_from_mailchimp
from utils.passwords import encode_password, random_password

log = logger(__name__)

retained_actions = {
    "agreement_accepted",
    "api_key_invalid",
    "api_key_unauthorized",
    "claim_practitioner_invite",
    "csv_file_missing_org",
    "finished_census_file_processing",
    "gift_purchased",
    "login",
    "marketing_push_send",
    "opentok_create_session",
    "opentok_create_token",
    "password_changed",
    "password_reset",
    "problem_bulk_cx_message",
    "rename_initial_csv_file",
    "success_bulk_cx_message",
    "user_added",
}
deleted_actions = {
    "appointment_cancel",
    "appointment_completion",
    "appointment_create_failure",
    "appointment_edit",
    "availability_removed",
    "get_org_employees",
    "message_credit_refunded",
    "message_fee_collected",
    "payment_swap_stripe_id",
    "reset_failed_payment",
    "reset_recurring_failed",
    "schedule_events_conflict",
    "schedule_events_create",
    "started_census_file_processing",
    "user_post_creation_complete",
    "user_post_creation_tagged",
}
assert (
    len(retained_actions & deleted_actions) == 0
), "Retained and deleted actions must be mutually exclusive."
known_actions = retained_actions | deleted_actions


def update_gdpr_request_status(user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user_delete_request = GDPRUserRequest.query.filter_by(user_id=user.id).one_or_none()
    if not user_delete_request:
        log.warning(
            f"No request is submitted for user {user.id} to gdpr_user_request table."
        )
    else:
        user_delete_request.status = GDPRRequestStatus.COMPLETED
        db.session.add(user_delete_request)


def delete_user(programmer_acknowledgement, initiator, user_id, email):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.debug(f"Deleting user ({user_id}) initiated by user ({initiator.id}).")

    assert (
        programmer_acknowledgement == "YES_I_AM_SURE"
    ), "This function is particularly destructive, so you must pass a magic string acknowledging its use."

    user = _must_be_forgettable(user_id, email)
    update_gdpr_request_status(user)
    if _has_medical_data(user):
        log.debug(f"User ({user_id}) has medical data.")
        op = _DeleteMedicalUser(initiator, user)
    else:
        log.debug(f"User ({user_id}) does not have medical data.")
        op = _DeleteNonMedicalUser(initiator, user)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "_DeleteNonMedicalUser", variable has type "_DeleteMedicalUser")

    audit_record = op.delete()
    return audit_record


@ddtrace.tracer.wrap()
def gdpr_delete_user(
    programmer_acknowledgement: str,
    initiator: User,
    user_id: int,
    email: str,
    requested_date: date,
    delete_idp: bool = False,
) -> None:
    log.debug(f"Deleting user ({user_id}) initiated by user ({initiator.id}).")

    assert (
        programmer_acknowledgement == "YES_I_AM_SURE"
    ), "This function is particularly destructive, so you must pass a magic string acknowledging its use."

    user = _get_forgettable_user(user_id, email)
    update_gdpr_request_status(user)
    op = GDPRDeleteUser(initiator, user, requested_date)
    # we don't need the returned values (list of deletion order) anywhere, so we don't capture it
    op.delete()
    if delete_idp:
        gdpr_data_delete = GDPRDataDelete()
        gdpr_data_delete.delete(user_id)
    return


def _get_forgettable_user(user_id: int, email: str) -> User:
    user = db.session.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        raise DeleteUserActionableError(
            f"The user with id ({user_id}) could not be found."
        )
    if user.email != email:
        log.warn(f"The given email is different from the user's (id: {user_id}) email")
    return user


# Is this user in a state we're willing to delete?
def _must_be_forgettable(user_id, email):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    user = (
        db.session.query(User)
        .filter(User.id == user_id, User.email == email)
        .one_or_none()
    )
    if user is None:
        raise DeleteUserActionableError(
            f"A user with id ({user_id}) and email ({email}) could not be found."
        )

    if not user.active:
        raise DeleteUserActionableError(
            f"You cannot delete an inactive user. A user with id {user_id} and email {email} is already inactive."
        )

    if not user.is_member or user.is_practitioner:
        raise DeleteUserActionableError(
            "Only members can be forgotten. Use practitioner deactivation for practitioners."
        )

    if Appointment.pending_for_user(user):
        raise DeleteUserActionableError(
            "User must cancel or follow through with pending appointments."
        )

    unpaid_incentives = (
        IncentivePayment.query.join(IncentivePayment.referral_code_use)
        .filter(
            ReferralCodeUse.user_id == user_id,
            IncentivePayment.incentive_paid.is_(False),
        )
        .all()
    )
    if unpaid_incentives:
        raise DeleteUserActionableError(
            f"User has been granted {len(unpaid_incentives)} incentive payment(s) that have not been paid yet."
        )

    return user


def _has_medical_data(user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return any(
        Model.retain_data_for_user(user)
        for Model in [
            Appointment,
            Message,
            PaymentAccountingEntry,
            CareProgram,
            NeedsAssessment,
            MemberTrack,
        ]
    )


class _DeleteUser(object):
    def __init__(self, initiator, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.user_id = user.id
        self.user = user
        self.data = {
            "identifiers": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "middle_name": user.middle_name,
                "last_name": user.last_name,
            },
            "initiator": initiator.id,
            "posts": [],
        }

    def delete(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.debug(f"Deleting internal data for user ({self.user_id}).")
        self._delete_internal()
        log.debug(f"Deleting external data for user ({self.user_id}).")
        self._delete_external()
        log.debug(f"Deleting user model ({self.user_id}).")
        self._delete_user()
        log.debug(f"Recording delete audit for user ({self.user_id}).")
        a = self._record_action()
        log.debug(f"Deleted all data for user ({self.user_id}).")
        return a

    def _delete_internal(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # Needs Assessment
        (
            db.session.query(NeedsAssessment)
            .filter(
                NeedsAssessment.appointment_id.is_(None),
                NeedsAssessment.id.in_(
                    [
                        na.id
                        for na in NeedsAssessment.list_by_user_and_kind(
                            user=self.user, is_medical=False
                        )
                        .options(load_only("id"))
                        .all()
                    ]
                ),
            )
            .delete(synchronize_session="fetch")
        )

        # Forum Post
        default_cc = AssignableAdvocate.default_care_coordinator()
        if default_cc:
            default_cc_id = default_cc.id
        posts = db.session.query(Post).filter(Post.author_id == self.user_id).all()
        for p in posts:
            self.data["posts"].append(p.id)
            p.anonymous = True
            p.author_id = default_cc_id

        # Member Preference
        pref_repo = MemberPreferencesRepository()
        pref_repo.delete_by_member_id(member_id=self.user_id)

        # Member Profile
        (
            db.session.query(MemberProfile)
            .filter(MemberProfile.user_id == self.user_id)
            .delete()
        )

        # Address
        (db.session.query(Address).filter(Address.user_id == self.user_id).delete())

        # IncentivePayment
        (
            IncentivePayment.query.filter(
                IncentivePayment.referral_code_use_id.in_(
                    db.session.query(ReferralCodeUse.id).filter_by(user_id=self.user_id)
                )
            ).delete(synchronize_session="fetch")
        )

        # ReferralCode
        referral_codes = (
            db.session.query(ReferralCode)
            .filter(ReferralCode.user_id == self.user_id)
            .all()
        )
        for rc in referral_codes:
            if rc.uses:
                rc.user_id = None
                continue
            for v in rc.values:
                db.session.delete(v)
            db.session.delete(rc)

        # Device
        (
            db.session.query(Device)
            .filter(Device.user_id == self.user_id)
            .delete(synchronize_session="fetch")
        )

        # UserInstallAttribution
        (
            db.session.query(UserInstallAttribution)
            .filter(UserInstallAttribution.user_id == self.user_id)
            .delete(synchronize_session="fetch")
        )

        # Agreement Acceptances
        (
            db.session.query(AgreementAcceptance)
            .filter(AgreementAcceptance.user_id == self.user_id)
            .delete(synchronize_session="fetch")
        )

    def _delete_external(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation

        # Auth0: deleting the user authentication record
        auth_service = authn.AuthenticationService()
        auth_service.delete_user(user_id=self.user.id)

        # MailChimp
        unsubscribe_user_from_mailchimp(self.user)

        # Zendesk
        messaging.services.zendesk.permanently_delete_user(self.user)

        # Braze
        braze_client = client.BrazeClient()
        braze_client.delete_user(external_id=self.user.esp_id)

        # SMS
        sms.permanently_delete_messages_for_user(self.user_id)

        # Stripe
        # Unlike other objects, deleted customers can still be retrieved through the API, in order to be
        # able to track the history of customers while still removing their credit card details and
        # preventing any further operations to be performed (such as adding a new subscription).
        StripeCustomerClient(PAYMENTS_STRIPE_API_KEY).delete_customer(user=self.user)
        # We also choose to unset member's connect account information instead of deleting it.
        # If the user adds back their account, it will create a new (duplicate) connect account.
        StripeConnectClient.unset_bank_account_for_user(self.user)

    def _delete_user(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        raise NotImplementedError()

    def _record_action(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        audit_log_info = {
            "user_id": self.user_id,
            "action_type": self._action_type(),
            "action_target_type": "user",
            "action_target_id": self.user_id,
        }
        log.info("audit_log_events", audit_log_info=audit_log_info)
        return audit_log_info

    def _action_type(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        raise NotImplementedError()


class _DeleteMedicalUser(_DeleteUser):
    def _action_type(self) -> str:
        return "delete_medical_user"

    def _delete_user(self) -> None:
        self.user.esp_id = str(uuid.uuid4())
        self.user.first_name = None
        self.user.middle_name = None
        self.user.last_name = None
        self.user.username = None
        self.user.active = False
        self.user.email_confirmed = True
        self.user.email = f"hello+GDPR_{uuid.uuid4()}@mavenclinic.com"
        self.user.password = encode_password(random_password())
        self.user.api_key = None
        self.user.image_id = None
        self.user.otp_secret = None

    def _delete_internal(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        super()._delete_internal()

        # Credit, ReferralCodeUse
        keep_credits = (
            db.session.query(Credit.id, Credit.referral_code_use_id)
            .filter(
                Credit.user_id == self.user_id,
                Credit.message_billing_id.isnot(None)
                | Credit.appointment_id.isnot(None),
            )
            .all()
        )
        keep_credit_ids = [r.id for r in keep_credits]
        keep_use_ids = set(r.referral_code_use_id for r in keep_credits)
        (
            db.session.query(Credit)
            .filter(Credit.user_id == self.user_id, Credit.id.notin_(keep_credit_ids))
            .delete(synchronize_session="fetch")
        )
        (
            db.session.query(ReferralCodeUse)
            .filter(
                ReferralCodeUse.user_id == self.user_id,
                ReferralCodeUse.id.notin_(keep_use_ids),
            )
            .delete(synchronize_session="fetch")
        )


class _DeleteNonMedicalUser(_DeleteUser):
    def _action_type(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return "delete_non_medical_user"

    def _delete_user(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        db.session.delete(self.user)

    def _delete_internal(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        super()._delete_internal()

        # Credits
        (
            db.session.query(Credit)
            .filter(Credit.user_id == self.user_id)
            .delete(synchronize_session="fetch")
        )

        # MessageCredit
        (
            db.session.query(MessageCredit)
            .filter(MessageCredit.user_id == self.user_id)
            .delete(synchronize_session="fetch")
        )

        # ReferralCodeUse
        (
            db.session.query(ReferralCodeUse)
            .filter(ReferralCodeUse.user_id == self.user_id)
            .delete(synchronize_session="fetch")
        )

        # MessageBilling
        (
            db.session.query(MessageBilling)
            .filter(MessageBilling.user_id == self.user_id)
            .delete(synchronize_session="fetch")
        )

        # Schedule, Appointment, PractitionerAppointmentAcks, NeedsAssessment
        user_appointments = Appointment.member_schedule_id.in_(
            db.session.query(Schedule.id)
            .filter(Schedule.user_id == self.user_id)
            .subquery()
        ) & ~exists().where(NeedsAssessment.appointment_id == Appointment.id)
        appointment_ids = [a.id for a in Appointment.query.filter(user_appointments)]
        (
            db.session.query(PractitionerAppointmentAck)
            .filter(PractitionerAppointmentAck.appointment_id.in_(appointment_ids))
            .delete(synchronize_session="fetch")
        )
        (
            db.session.query(Appointment)
            .filter(Appointment.id.in_(appointment_ids))
            .delete(synchronize_session="fetch")
        )
        (
            db.session.query(Schedule.id)
            .filter(
                Schedule.user_id == self.user_id,
                ~exists().where(Appointment.member_schedule_id == Schedule.id),
            )
            .delete(synchronize_session="fetch")
        )

        # Message, MessageUsers, Channel, ChannelUsers
        channel_ids = [
            cu.channel_id
            for cu in db.session.query(ChannelUsers.channel_id)
            .filter(ChannelUsers.user_id == self.user_id)
            .all()
        ]
        (
            db.session.query(ChannelUsers)
            .filter(ChannelUsers.channel_id.in_(channel_ids))
            .delete(synchronize_session="fetch")
        )
        message_ids = [
            m.id
            for m in db.session.query(Message)
            .filter(Message.channel_id.in_(channel_ids))
            .all()
        ]
        (
            db.session.query(MessageUsers)
            .filter(MessageUsers.message_id.in_(message_ids))
            .delete(synchronize_session="fetch")
        )
        (
            db.session.query(Message)
            .filter(Message.id.in_(message_ids))
            .delete(synchronize_session="fetch")
        )
        (
            db.session.query(Channel)
            .filter(Channel.id.in_(channel_ids))
            .delete(synchronize_session="fetch")
        )

        # Member Care Team
        (
            db.session.query(MemberPractitionerAssociation)
            .filter(MemberPractitionerAssociation.user_id == self.user_id)
            .delete(synchronize_session="fetch")
        )
        log.info("Deleting rows in MemberPractitionerAssociation", user_id=self.user_id)

        # Health Profile
        (
            db.session.query(HealthProfile)
            .filter(HealthProfile.user_id == self.user_id)
            .delete(synchronize_session="fetch")
        )

        # User Onboarding
        (
            db.session.query(UserOnboardingState)
            .filter(UserOnboardingState.user_id == self.user_id)
            .delete(synchronize_session="fetch")
        )
