import json
from string import Template

import arrow
import flask_babel
from maven import feature_flags

from authn.models.user import User
from care_advocates.models.transitions import (
    CareAdvocateMemberTransitionLog,
    CareAdvocateMemberTransitionResponse,
    CareAdvocateMemberTransitionSender,
)
from care_advocates.services.transition_log import (
    CareAdvocateMemberTransitionValidator,
    TransitionLogValidatorError,
)
from l10n.db_strings.translate import TranslateDBFields
from messaging.models.messaging import Channel, Message
from models.profiles import CareTeamTypes, MemberPractitionerAssociation
from storage.connection import db
from tasks.messaging import send_to_zendesk
from tasks.notifications import notify_new_message
from tasks.queues import job
from user_locale.services.locale_preference_service import LocalePreferenceService
from utils.log import logger
from utils.mail import send_message

log = logger(__name__)


@job
def perform_care_advocate_member_transitions():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Grab any scheduled transitions that have passed their scheduled time, and haven't been run yet.
    transitions_to_run = CareAdvocateMemberTransitionLog.query.filter(
        CareAdvocateMemberTransitionLog.date_scheduled < arrow.utcnow().datetime,
        CareAdvocateMemberTransitionLog.date_completed.is_(None),
    )

    # These maps will be used to keep track of the various results we see from our transitions.
    #
    # `results_per_member` will be a map of { CareAdvocateMemberTransitionResponse.value -> List<member_id> },
    # effectively keeping track of the list of members whose transitions had a particular success/error state.
    #
    # `results_per_user` will be a map of
    # { transition_scheduler_id -> { CareAdvocateMemberTransitionResponse.value -> List<Tuple<member_id, old_cx_id, new_cx_id>> } },
    # effectively keeping track of the mapping of success/error states to the list of transition arguments that
    # produced that success/error state, but doing so on a per-transition-scheduler basis, where the
    # `transition_scheduler` is the user that uploaded the transition CSV and scheduled the transitions.
    #
    # `results_per_member` will be used purely for logging purposes, while `results_per_user` will be used
    # when sending the transition schedulers emails about the success and error breakdown of the transitions
    # that they scheduled.
    results_per_member = {}
    results_per_user = {}
    if transitions_to_run:

        for transition_to_run in transitions_to_run:
            transition_scheduler_id = transition_to_run.user_id
            pending_transitions = []
            all_user_ids = set()
            transition_validator = CareAdvocateMemberTransitionValidator()

            transition_rows = json.loads(transition_to_run.uploaded_content)
            for transition_row in transition_rows:
                pending_transition = {
                    "member_id": transition_row.get("member_id"),
                    "old_cx_id": transition_row.get("old_cx_id"),
                    "new_cx_id": transition_row.get("new_cx_id"),
                    "messaging": transition_row.get("messaging"),
                }
                pending_transitions.append(pending_transition)
                all_user_ids.add(pending_transition["member_id"])
                all_user_ids.add(pending_transition["old_cx_id"])
                all_user_ids.add(pending_transition["new_cx_id"])

            all_users = {
                u.id: u for u in User.query.filter(User.id.in_(list(all_user_ids)))
            }
            for pending_transition in pending_transitions:
                member_id = pending_transition["member_id"]
                old_cx_id = pending_transition["old_cx_id"]
                new_cx_id = pending_transition["new_cx_id"]
                messaging = pending_transition["messaging"]
                member = all_users[member_id] if member_id in all_users else None
                old_cx = all_users[old_cx_id] if old_cx_id in all_users else None
                new_cx = all_users[new_cx_id] if new_cx_id in all_users else None
                message_types = messaging.split(";") if messaging else []

                # Run through the validator
                validation_message = transition_validator.validate(
                    member,
                    old_cx,
                    new_cx,
                    message_types,
                    record=pending_transition,
                )
                if validation_message:
                    _record_result_for_member(
                        results_per_member,
                        member_id,
                        validation_message.message_name,
                    )
                    _record_result_for_user(
                        results_per_user,
                        transition_scheduler_id,
                        member_id,
                        old_cx_id,
                        new_cx_id,
                        validation_message.message_name,
                    )
                    continue

                messages_to_send = []
                for message_template in transition_validator.message_templates:
                    if message_template in message_types:
                        messages_to_send.append(
                            transition_validator.message_templates[message_template]
                        )

                l10n_flag = feature_flags.bool_variation(
                    "release-disco-be-localization",
                    default=False,
                )
                result = reassign_care_advocate(
                    member=member,
                    old_cx=old_cx,
                    new_cx=new_cx,
                    message_templates=messages_to_send,  # type: ignore[arg-type] # Argument "message_templates" to "reassign_care_advocate" has incompatible type "List[Any]"; expected "Dict[Any, Any]"
                    l10n_flag=l10n_flag,
                )

                _record_result_for_member(
                    results_per_member,
                    member_id,
                    result,
                )

                _record_result_for_user(
                    results_per_user,
                    transition_scheduler_id,
                    member_id,
                    old_cx_id,
                    new_cx_id,
                    result,
                )

            transition_to_run.date_completed = arrow.utcnow().datetime
            db.session.add(transition_to_run)
            db.session.commit()

        log.info("Completed care advocate reassignments", results=results_per_member)

        # Send email to any user who scheduled this CA transition
        for (transition_scheduler_id, results_map) in results_per_user.items():
            transition_scheduler = User.query.get(transition_scheduler_id)
            successes, failures = _calculate_successes_and_failures(results_map)
            email_text = _craft_email_body(successes, failures, results_map)
            email_subject = _craft_email_subject(successes, failures)

            log.info(
                "Sending care advocate reassignment email",
                subject=email_subject,
                to_email=transition_scheduler.email,
            )

            send_message(
                to_email=transition_scheduler.email,
                subject=email_subject,
                text=email_text,
                internal_alert=True,
            )

            # Also send a copy of this email to disco team
            send_message(
                to_email="pod-care-discovery@mavenclinic.com",
                subject=email_subject,
                text=email_text,
                internal_alert=True,
            )

    return results_per_member, results_per_user


def _record_result_for_member(results, member_id, result):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if result not in results:
        results[result] = []
    results[result].append(member_id)


def _record_result_for_user(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    results_per_user,
    transition_scheduler_id,
    member_id,
    old_cx_id,
    new_cx_id,
    result,
):
    if transition_scheduler_id not in results_per_user:
        results_per_user[transition_scheduler_id] = {}
    if result not in results_per_user[transition_scheduler_id]:
        results_per_user[transition_scheduler_id][result] = []
    results_per_user[transition_scheduler_id][result].append(
        (member_id, old_cx_id, new_cx_id)
    )


def _calculate_successes_and_failures(results_map):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    successes = 0
    failures = 0

    for (result, member_tuple_list) in results_map.items():
        transition_count_for_result = len(member_tuple_list)

        if result == CareAdvocateMemberTransitionResponse.SUCCESS.name:
            successes += transition_count_for_result
        else:
            failures += transition_count_for_result

    return (successes, failures)


def _craft_email_subject(successes, failures):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    successes_string = "success" if successes == 1 else "successes"
    failures_string = "failure" if failures == 1 else "failures"
    return f"Care advocate member transitions completed: {successes} {successes_string}, {failures} {failures_string}"


def _craft_email_body(successes, failures, results_map):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    body = _craft_email_subject(successes, failures) + "\n\n"

    for (result, member_tuple_list) in results_map.items():
        if result != CareAdvocateMemberTransitionResponse.SUCCESS.name:
            if getattr(TransitionLogValidatorError, result):
                error = getattr(TransitionLogValidatorError, result).value
            else:
                error = result
            body += f'Error "{error}":\n'
            for (member_id, old_cx_id, new_cx_id) in member_tuple_list:
                body += (
                    f"\tMember {member_id}, Old CX {old_cx_id}, New CX {new_cx_id}\n"
                )
            body += "\n"

    return body


def reassign_care_advocate(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    member: User,
    old_cx: User,
    new_cx: User,
    message_templates: dict,
    l10n_flag: bool = False,
):
    log.info(
        "Reassigning member's care advocate.",
        user_id=member.id,
        old_cx_id=old_cx.id,
        new_cx_id=new_cx.id,
        sending_message=bool(message_templates),
        message_templates=message_templates,
        l10n_flag=l10n_flag,
    )

    try:
        association = MemberPractitionerAssociation.query.filter_by(
            user_id=member.id,
            practitioner_id=old_cx.id,
            type=CareTeamTypes.CARE_COORDINATOR,
        ).first()
        association.practitioner_id = new_cx.id
        db.session.commit()
        log.info(
            "Updated member practitioner association to new_cx.",
            mpa_id=association.id,
            user_id=member.id,
            old_cx_id=old_cx.id,
            new_cx_id=new_cx.id,
        )
    except Exception as e:
        log.error(
            CareAdvocateMemberTransitionResponse.REASSIGN_EXCEPTION.name,
            exception=e,
            old_cx_id=old_cx.id,
            new_cx_id=new_cx.id,
            user_id=member.id,
        )
        return CareAdvocateMemberTransitionResponse.REASSIGN_EXCEPTION.name

    sender_mapping = {
        CareAdvocateMemberTransitionSender.OLD_CX.name: old_cx,
        CareAdvocateMemberTransitionSender.NEW_CX.name: new_cx,
    }

    template_mapping = {
        "MEMBER_FIRST_NAME": member.first_name,
        "OLD_CX_FIRST_NAME": old_cx.first_name,
        "NEW_CX_FIRST_NAME": new_cx.first_name,
    }
    for message_template in message_templates:
        sender = sender_mapping[message_template.sender.name]

        if l10n_flag and (
            member_locale := LocalePreferenceService.get_preferred_locale_for_user(
                member
            )
        ):
            with flask_babel.force_locale(member_locale):
                message_body = TranslateDBFields().get_translated_ca_member_transition(
                    message_template.slug,
                    "message_body",
                    message_template.message_body,
                )
        else:
            message_body = message_template.message_body

        # Turn the body into a template for name substitions
        body = Template(message_body).substitute(template_mapping)
        message_result = _send_member_message(sender, member, body)
        if message_result == CareAdvocateMemberTransitionResponse.MESSAGE_EXCEPTION:
            return message_result.name

    # Success if we didn't return False yet
    return CareAdvocateMemberTransitionResponse.SUCCESS.name


def _send_member_message(
    sender: User, member: User, body: str
) -> CareAdvocateMemberTransitionResponse:
    try:
        log.info(
            "Sending message to member regarding care advocate reassignment.",
            sender_id=sender.id,
            user_id=member.id,
        )
        channel = Channel.get_or_create_channel(sender, [member])
        message = Message(user=sender, channel=channel, body=body)
        db.session.add(message)
        db.session.commit()

        notify_new_message.delay(
            member.id,
            message.id,
            service_ns="admin_care_advocate_member_transitions",
            team_ns="care_discovery",
        )
        send_to_zendesk.delay(
            message.id,
            initial_cx_message=True,
            user_need_when_solving_ticket="customer-need-member-proactive-outreach-care-team-update",
            service_ns="admin_care_advocate_member_transitions",
            team_ns="care_discovery",
            caller="reassign_care_advocate",
        )
        log.info(
            "Sent advocate reassignment message.",
            user_id=member.id,
            message_id=message.id,
        )

    except Exception as e:
        log.error(
            CareAdvocateMemberTransitionResponse.MESSAGE_EXCEPTION,
            user_id=member.id,
            exception=e,
        )
        return CareAdvocateMemberTransitionResponse.MESSAGE_EXCEPTION
    return  # type: ignore[return-value] # Return value expected
