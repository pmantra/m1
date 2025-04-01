from maven import feature_flags
from sqlalchemy.exc import SQLAlchemyError

from appointments.models.cancellation_policy import (
    CancellationPolicy,
    CancellationPolicyName,
)
from appointments.models.payments import new_stripe_customer
from authn.models.user import User
from common.services.stripe_constants import PAYMENTS_STRIPE_API_KEY
from messaging.models.messaging import ChannelUsers
from messaging.services.zendesk import get_or_create_zenpy_user
from models.profiles import CareTeamTypes, MemberPractitionerAssociation
from models.referrals import add_referral_code_for_user
from payments.models.practitioner_contract import ContractType
from storage.connection import db
from tasks.helpers import get_user
from tasks.marketing import track_user_in_braze
from tasks.queues import job
from tasks.zendesk_v2 import tag_practitioner_in_zendesk
from utils import braze_events
from utils.flag_groups import ZENDESK_USER_PROFILE
from utils.log import logger

log = logger(__name__)


def should_enable_zendesk_user_profile_creation() -> bool:
    return feature_flags.bool_variation(
        flag_key=ZENDESK_USER_PROFILE.CREATED_ZENDESK_USER_PROFILE_POST_USER_CREATION,
        default=False,
    )


@job(team_ns="enrollments")
def user_post_creation(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Finish user post creation tasks.
    :param user_id: id of the user
    :return: None
    """
    try:
        user = get_user(user_id)
        if user:
            if user.member_profile:
                profile = user.member_profile

                if should_enable_zendesk_user_profile_creation():
                    # create a ZendeskUser profile for the member
                    zendesk_user = get_or_create_zenpy_user(user=user)

                    log.info(
                        "Created a new Zendesk User profile for member",
                        zendesk_user_id=zendesk_user.id,
                        user_id=user_id,
                        created_with_phone_number=profile.phone_number is not None,
                    )

                if profile.stripe_customer_id:
                    log.info("User already has stripe ID...", user_id=user_id)
                elif PAYMENTS_STRIPE_API_KEY is not None:
                    profile.stripe_customer_id = new_stripe_customer(user)
                else:
                    log.info(
                        "Failed to create stripe user -- no api key available.",
                        user_id=user_id,
                    )

            if user.practitioner_profile:
                tag_practitioner_in_zendesk.delay(user.id, team_ns="virtual_care")

                profile = user.practitioner_profile
                if not profile.default_cancellation_policy:
                    cancellation_policy_name = CancellationPolicyName.default().value
                    if (
                        profile.active_contract
                        and profile.active_contract.contract_type
                        in [ContractType.HYBRID_1_0, ContractType.HYBRID_2_0]
                    ):
                        cancellation_policy_name = CancellationPolicyName.FLEXIBLE.value

                    default_policy = (
                        db.session.query(CancellationPolicy)
                        .filter(CancellationPolicy.name == cancellation_policy_name)
                        .first()
                    )
                    profile.default_cancellation_policy = default_policy
                    db.session.add(profile)

            add_referral_code_for_user(user.id)

            db.session.add(user)
            db.session.commit()

            track_user_in_braze(user_id)

            log.info("Finished post-creation tasks for user", user_id=user.id)
            return user
    except SQLAlchemyError as exc:
        log.warning("Failed user_post_creation for user %s", user_id)
        log.info(exc)


@job(traced_parameters=("user_id",))
def send_password_reset(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    user = User.query.get(user_id)
    braze_events.password_reset(user)


@job("priority", traced_parameters=("user_id",))
def send_existing_fertility_user_password_reset(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    user = User.query.get(user_id)
    braze_events.existing_fertility_user_password_reset(user)


@job(traced_parameters=("user_id",))
def send_password_changed(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    user = User.query.get(user_id)
    braze_events.password_updated(user)


def find_messaging_care_team_with_empty_channels():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    to_be_removed = []
    care_team_via_message = MemberPractitionerAssociation.query.filter(
        MemberPractitionerAssociation.type == CareTeamTypes.MESSAGE
    ).all()
    log.info(
        "Querying rows in MemberPractitionerAssociation", type_=CareTeamTypes.MESSAGE
    )

    log.debug(
        "Total of %s message type care team practitioners", len(care_team_via_message)
    )
    for ct in care_team_via_message:
        channel = ChannelUsers.find_existing_channel([ct.user_id, ct.practitioner_id])

        if not channel:
            log.debug("Something went wrong, %s did not have a chanel!", ct)
            to_be_removed.append(ct)
        else:
            if not channel.messages:
                log.debug("%s created from an empty channel.", ct)
                to_be_removed.append(ct)

    return to_be_removed


@job
def fix_member_care_team_empty_channel():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    to_be_removed = find_messaging_care_team_with_empty_channels()
    log.debug(
        "Removing %s member/practitioner associations "
        "due to empty message channels.",
        len(to_be_removed),
    )

    for each in to_be_removed:
        db.session.delete(each)

    db.session.commit()
    log.debug("Done!")
