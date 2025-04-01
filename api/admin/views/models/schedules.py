import datetime
from typing import Type

import flask_login as login
from flask import abort, flash, redirect, request, url_for
from flask_admin import expose
from flask_admin.actions import action
from flask_admin.form import rules
from flask_admin.model.helpers import get_mdict_item_or_list
from markupsafe import Markup
from maven import feature_flags
from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound
from wtforms import fields, validators

from admin.common import https_url, is_enterprise_cc_appointment
from admin.views.base import (
    AdminCategory,
    AdminViewT,
    ContainsFilter,
    IsFilter,
    MavenAuditedView,
)
from admin.views.models.phone import PhoneNumberFilter
from appointments.models.appointment import Appointment
from appointments.models.appointment_meta_data import AppointmentMetaData
from appointments.models.availability_notification_request import (
    AvailabilityNotificationRequest,
)
from appointments.models.constants import APPOINTMENT_STATES
from appointments.models.payments import Credit
from appointments.models.practitioner_appointment import PractitionerAppointmentAck
from appointments.models.reschedule_history import RescheduleHistory
from appointments.models.schedule import Schedule
from appointments.utils.redis_util import invalidate_appointment_cache
from audit_log.utils import emit_bulk_audit_log_read
from authn.models.user import User
from authz.models.roles import ROLES, Role
from common.models.scheduled_maintenance import ScheduledMaintenance
from common.stats import PodNames, increment
from eligibility import EnterpriseVerificationService, get_verification_service
from messaging.models.messaging import Message
from models.products import Product
from models.questionnaires import Questionnaire, RecordedAnswerSet
from payments.services.appointment_payments import AppointmentPaymentsService
from providers.service.provider import ProviderService
from storage.connection import RoutingSQLAlchemy, db
from utils.launchdarkly import user_context
from utils.log import logger

log = logger(__name__)


class AppointmentViewMemberLastNameFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.filter(
            Appointment.member_schedule_id.in_(
                db.session.query(Schedule.id)
                .join(User)
                .filter(User.last_name.contains(value))
            )
        )


class AppointmentViewMemberFirstNameFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.filter(
            Appointment.member_schedule_id.in_(
                db.session.query(Schedule.id)
                .join(User)
                .filter(User.first_name.contains(value))
            )
        )


class AppointmentViewMemberEmailFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.filter(
            Appointment.member_schedule_id.in_(
                db.session.query(Schedule.id)
                .join(User)
                .filter(User.email.contains(value))
            )
        )


class AppointmentViewMemberIdSearch(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(Schedule).filter(Schedule.user_id == value)


class AppointmentViewPractitionerLastNameFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user_alias = aliased(User)
        product_alias = aliased(Product)
        return (
            query.join(product_alias)
            .join(user_alias)
            .filter(user_alias.last_name.contains(value))
        )


class AppointmentViewPractitionerFirstNameFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user_alias = aliased(User)
        product_alias = aliased(Product)
        return (
            query.join(product_alias)
            .join(user_alias)
            .filter(user_alias.first_name.contains(value))
        )


class AppointmentViewPractitionerEmailFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user_alias = aliased(User)
        product_alias = aliased(Product)
        return (
            query.join(product_alias)
            .join(user_alias)
            .filter(user_alias.email.contains(value))
        )


class AppointmentViewPractitionerIdSearch(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        product_alias = aliased(Product)
        return query.join(product_alias).filter(product_alias.user_id == value)


class AppointmentView(MavenAuditedView):
    read_permission = "read:appointment"
    edit_permission = "edit:appointment"

    list_template = "appointment_list_template.html"
    edit_template = "appointment_edit_template.html"

    action_disallowed_list = ["delete"]
    column_sortable_list = ("id", "scheduled_start", "scheduled_end", "cancelled_at")
    column_list = (
        "id",
        "api_id",
        "practitioner.full_name",
        "practitioner_id",
        "member.email",
        "member.full_name",
        "member_id",
        "scheduled_start",
        "scheduled_end",
        "cancelled_at",
        "state",
    )
    column_filters = (
        "id",
        "api_id",
        "scheduled_start",
        "scheduled_end",
        AppointmentViewMemberFirstNameFilter(None, "Member First Name"),
        AppointmentViewMemberLastNameFilter(None, "Member Last Name"),
        AppointmentViewMemberEmailFilter(None, "Member Email"),
        AppointmentViewMemberIdSearch(None, "Member User ID search"),
        AppointmentViewPractitionerFirstNameFilter(None, "Practitioner First Name"),
        AppointmentViewPractitionerLastNameFilter(None, "Practitioner Last Name"),
        AppointmentViewPractitionerEmailFilter(None, "Practitioner Email"),
        AppointmentViewPractitionerIdSearch(None, "Practitioner User ID search"),
    )

    form_columns = ["disputed_at", "admin_comments", "purpose"]

    form_choices = {
        "purpose": [
            ("birth_planning", "Birth Planning"),
            ("childbirth_ed", "Childbirth Education"),
            ("pediatric_prenatal_consult", "Pediatric Prenatal Consult"),
            ("postpartum_planning", "Postpartum Planning"),
            ("introduction", "Introduction"),
            ("birth_needs_assessment", "Pregnancy Needs Assessment"),
            ("postpartum_needs_assessment", "Postpartum Needs Assessment"),
            ("introduction_egg_freezing", "Introduction (Egg Freezing)"),
            ("introduction_fertility", "Introduction (Fertility)"),
            ("introduction_menopause", "Introduction (Menopause)"),
        ]
    }

    named_filter_urls = True

    @expose("/list_view_appointments")
    def get_list_view_appointments(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        view_args = self._get_list_extra_args()
        sort_column = self._get_column_by_idx(view_args.sort)
        if sort_column is not None:
            sort_column = sort_column[0]

        page_size = view_args.page_size or self.page_size

        count, data = self.get_list(
            view_args.page,
            sort_column,
            view_args.sort_desc,
            view_args.search,
            view_args.filters,
            page_size=page_size,
        )

        appointments = [
            {
                "ID": appt.id,
                "API_ID": appt.api_id,
                "Practitioner Name": appt.practitioner.full_name
                if appt.practitioner
                else "",
                "Practitioner ID": appt.practitioner.id if appt.practitioner else "",
                "Member Email": appt.member.email if appt.member else "",
                "Member Name": appt.member.full_name if appt.member else "",
                "Member ID": appt.member.id if appt.member else "",
                "Scheduled Start": appt.scheduled_start,
                "Scheduled End": appt.scheduled_end,
                "Cancelled At": appt.scheduled_start,
                "State": appt.state,
                "EditURL": url_for("appointment.edit_view", id=appt.id),
            }
            for appt in data
        ]

        if data:
            emit_bulk_audit_log_read(data)

        return {
            "data": {
                "items": appointments,
                "pagination": {
                    "limit": view_args.page_size,
                    "total": count,
                },
            }
        }

    @expose("/")
    def index_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation

        # to get sorting working you need to use the name of the field in the column_list, like the created_at here
        # also you need to set the field in the column_sortable_list matching the column_list
        columns = [col[0] for col in self.get_list_columns()]

        self._template_args["columns_conf"] = [
            {"label": "ID"},
            {"label": "API_ID"},
            {"label": "Practitioner Name"},
            {"label": "Practitioner ID"},
            {"label": "Member Email"},
            {"label": "Member Name"},
            {"label": "Member ID"},
            {
                "label": "Scheduled Start",
                "formatterType": "dateWithTimezone",
                "sort": columns.index("scheduled_start"),
            },
            {
                "label": "Scheduled End",
                "formatterType": "dateWithTimezone",
                "sort": columns.index("scheduled_end"),
            },
            {"label": "State"},
        ]

        # this are the values used by flask-admin
        self._template_args["can_delete"] = self.can_delete
        self._template_args["delete_conf"] = {
            "deleteFormUrl": "/admin/appointment/delete/",
            "hiddenUrl": "/admin/appointment/",
        }

        view_args = self._get_list_extra_args()
        self._template_args["view_args"] = {
            "page_size": view_args.page_size or 20,
            "filters": self._get_filters(view_args.filters),
            "sort": view_args.sort or "",
            "desc": view_args.sort_desc or "",
        }

        sort_column = self._get_column_by_idx(view_args.sort)
        if sort_column is not None:
            sort_column = sort_column[0]

        actions, _ = self.get_actions_list()
        self._template_args["has_actions"] = len(actions) > 0

        return super().index_view()

    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        appt_id = get_mdict_item_or_list(request.args, "id")

        if appt_id:
            appointment = self.get_one(appt_id)
            if appointment and is_enterprise_cc_appointment(appointment):
                self._template_args["show_cc_dashboard_link"] = True
            if ProviderService().enabled_for_prescribing(appointment.practitioner_id):
                self._template_args["show_rx_info"] = True

            reschedule_record = (
                db.session.query(RescheduleHistory)
                .filter(RescheduleHistory.appointment_id == appointment.id)
                .order_by(RescheduleHistory.id.desc())
                .first()
            )
            if reschedule_record is not None:
                self._template_args[
                    "rescheduled_from"
                ] = reschedule_record.scheduled_start
            else:
                # Show "None" if the appointment doesn't have any reschedule history
                self._template_args["rescheduled_from"] = "None"

        return super().edit_view()

    def _list_member_id(view, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return Markup(f"<p>{model.member.id}</p>")

    def _list_practitioner_id(view, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return Markup(f"<p>{model.practitioner.id}</p>")

    column_formatters = {
        "member_id": _list_member_id,
        "practitioner_id": _list_practitioner_id,
    }

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.staff_cost = fields.FloatField(validators=[validators.Optional()])
        return form_class

    @action(
        "reset_started_at",
        "Reset Started At",
        "This cannot be reversed and should be rare. Proceed?",
    )
    def reset_started_at(self, appointment_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if len(appointment_ids) != 1:
            log.debug("Too many IDS to reset_started_at: %s", appointment_ids)
            abort(400)
        else:
            appointment = (
                db.session.query(Appointment)
                .filter(Appointment.id == appointment_ids[0])
                .one()
            )
            now = datetime.datetime.utcnow()

            if "admin_resets" not in appointment.json:
                appointment.json["admin_resets"] = []

            appointment.json["admin_resets"].append(
                {
                    "type": "started_at",
                    "admin": login.current_user.id,
                    "reset_at": str(now),
                    "member_started": str(appointment.member_started_at),
                    "practitioner_started": str(appointment.practitioner_started_at),
                }
            )

            appointment.member_started_at = None
            appointment.practitioner_started_at = None

            db.session.add(appointment)
            db.session.commit()
            invalidate_appointment_cache(appointment)

    @action(
        "complete",
        "Complete Appointment",
        "This will result in a charge to the member. Proceed?",
    )
    def complete(self, appointment_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from appointments.tasks.appointments import appointment_completion

        if len(appointment_ids) != 1:
            log.debug("Too many IDS to complete: %s", appointment_ids)
            abort(400)
        else:
            appointment = (
                db.session.query(Appointment)
                .filter(Appointment.id == appointment_ids[0])
                .one()
            )
            now = datetime.datetime.utcnow()

            if appointment.state in (
                APPOINTMENT_STATES.payment_resolved,
                APPOINTMENT_STATES.cancelled,
            ):
                log.info("ADMIN Complete - Cannot complete %s", appointment)
                abort(400)

            if appointment.member_ended_at is None:
                appointment.member_ended_at = now
            if appointment.practitioner_ended_at is None:
                appointment.practitioner_ended_at = now

            if appointment.member_started_at is None:
                appointment.member_started_at = now
            if appointment.practitioner_started_at is None:
                appointment.practitioner_started_at = now

            appointment.json["admin_completion"] = {
                "user": login.current_user.id,
                "time": str(now),
            }
            db.session.add(appointment)
            db.session.commit()

            appointment_completion.delay(appointment.id)
            invalidate_appointment_cache(appointment)

    @action(
        "uncancel_appointment",
        "Un-cancel (Member Cancelled) ... Does nothing with fees/payments ",
        "This will remove cancelled at and cancelled by. It will also set "
        "the start/end times. Should be used for member cancellations "
        "where they paid but appointment happened. Proceed?",
    )
    def uncancel_appointment(self, appointment_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if len(appointment_ids) != 1:
            log.debug("Too many IDS to un-cancel: %s", appointment_ids)
            abort(400)

        appointment = Appointment.query.get(appointment_ids[0])
        if not appointment:
            log.warning("No appointment for %s", appointment_ids)
            abort(400)

        if appointment.cancelled_by_user_id != appointment.member.id:
            log.info("Not uncancelling - this was cancelled by practitioner.")
            flash("This appointment was cancelled by the practitioner!")
            abort(400)

        log.debug("Going to uncancel_appointment: %s", appointment)
        appointment.uncancel()

        now = datetime.datetime.utcnow()
        if appointment.scheduled_start < now:
            log.debug("%s in past, adding start/end times if needed", appointment)

            if appointment.member_ended_at is None:
                appointment.member_ended_at = now
            if appointment.practitioner_ended_at is None:
                appointment.practitioner_ended_at = now
            if appointment.member_started_at is None:
                appointment.member_started_at = now
            if appointment.practitioner_started_at is None:
                appointment.practitioner_started_at = now

        db.session.add(appointment)
        db.session.commit()
        invalidate_appointment_cache(appointment)
        log.debug("All set with uncancel_appointment: %s", appointment)
        flash(f"All set uncancelling {appointment}")

    @action(
        "uncancel_appointment_charge",
        "Un-cancel (Practitioner Cancelled) ... Reserve credits and swap payments",
        "This will un-cancel and also authorize payment again. It should be used "
        "for when the practitioner canceled but the appt happened. Proceed?",
    )
    def uncancel_appointment_charge(self, appointment_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation

        if len(appointment_ids) != 1:
            log.debug("Too many IDS to un-cancel and charge: %s", appointment_ids)
            abort(400)

        appointment = Appointment.query.get(appointment_ids[0])
        if not appointment:
            log.warning("No appointment for %s", appointment_ids)
            abort(400)

        if appointment.cancelled_by_user_id != appointment.practitioner.id:
            log.info("Not uncancelling - this was cancelled by member...")
            flash("This appointment was cancelled by the member!")
            abort(400)

        log.debug("Going to uncancel_appointment_charge: %s", appointment)
        appointment.uncancel()

        if appointment.payment:
            appointment.payment.swap_for_new_charge()

        if (appointment.payment is None) or (
            appointment.payment.amount < appointment.product.price
        ):
            AppointmentPaymentsService(session=db.session).reserve_credits(
                appointment_id=appointment.id,
                product_id=appointment.product_id,
                member_id=appointment.member_id,
                scheduled_start=appointment.scheduled_start,
            )
            invalidate_appointment_cache(appointment)
            db.session.commit()

        log.debug("All set with uncancel_appointment_charge: %s", appointment)
        flash(f"All set uncancelling {appointment} - You'll still need to complete it")

    @action(
        "cancel_as_member",
        "Cancel - MEMBER's Fault",
        "This may result in a charge to the member. Proceed?",
    )
    def cancel_as_member(self, appointment_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._cancel_appointment(appointment_ids, "member")

    @action(
        "cancel_as_practitioner",
        "Cancel - PRACTITIONER's Fault",
        "This will cancel on behalf of practitioner. Proceed?",
    )
    def cancel_as_practitioner(self, appointment_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._cancel_appointment(appointment_ids, "practitioner")

    def _cancel_appointment(self, appointment_ids, user_type):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from storage.connection import db

        if user_type not in ("member", "practitioner"):
            log.warning("Bad user_type in cancel appointment!")
            return

        if len(appointment_ids) != 1:
            log.debug(f"Too many IDS to cancel: {appointment_ids}")
            abort(400)
        else:
            appointment = Appointment.query.get(appointment_ids[0])
            if not appointment:
                log.warning(f"No appointment for {appointment_ids}")
                abort(400)
            else:
                cancellable_states = (
                    APPOINTMENT_STATES.scheduled,
                    APPOINTMENT_STATES.overdue,
                    APPOINTMENT_STATES.incomplete,
                    APPOINTMENT_STATES.occurring,
                    APPOINTMENT_STATES.overflowing,
                )
                if appointment.state not in cancellable_states:
                    log.info(f"ADMIN cancellation - Cannot cancel {appointment}")
                    abort(400)

                canceler = getattr(appointment, user_type)
                appointment.cancel(canceler.id, admin_initiated=True)
                db.session.add(appointment)
                db.session.commit()
                invalidate_appointment_cache(appointment)

    @action(
        "resolve_with_credit",
        "Resolve with credit",
        "This will resolve payment for these appointments using new credits. Proceed?",
    )
    def resolve_with_credit(self, appt_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for appointment in Appointment.query.filter(Appointment.id.in_(appt_ids)):
            if appointment.state != APPOINTMENT_STATES.payment_pending:
                flash(
                    f"Cannot resolve payment with credit for appointment {appointment} (not in state {APPOINTMENT_STATES.payment_pending})"
                )
                db.session.rollback()
                return redirect(https_url("appointment.index_view"))

            user = appointment.member
            verification = None
            # get verification for enterprise user
            if user and user.is_enterprise:
                verification_svc: EnterpriseVerificationService = (
                    get_verification_service()
                )
                verification = verification_svc.get_verification_for_user_and_org(
                    user_id=user.id,
                    organization_id=user.organization.id if user.organization else None,
                )

            db.session.add(
                Credit(
                    user=appointment.member,
                    appointment=appointment,
                    used_at=datetime.datetime.utcnow(),
                    amount=appointment.product.price,
                    eligibility_member_id=verification.eligibility_member_id
                    if verification
                    else None,
                    eligibility_verification_id=verification.verification_id
                    if verification
                    else None,
                    eligibility_member_2_id=verification.eligibility_member_2_id
                    if verification
                    else None,
                    eligibility_verification_2_id=verification.verification_2_id
                    if verification
                    else None,
                    eligibility_member_2_version=verification.eligibility_member_2_version
                    if verification
                    else None,
                )
            )
            invalidate_appointment_cache(appointment)

        db.session.commit()

        flash(f"Successfully resolved payment for appointments: {appt_ids}")
        return redirect(https_url("appointment.index_view"))

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            Appointment,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class AppointmentMetaDataView(MavenAuditedView):
    read_permission = "read:appointment-notes"
    edit_permission = "edit:appointment-notes"

    edit_template = "appointment_metadata_edit.html"
    column_list = ("id", "appointment_id", "type", "content", "draft")
    column_filters = ("appointment_id", "id")
    form_columns = ("id", "type", "content")
    action_disallowed_list = ["delete"]
    form_widget_args = {"id": {"readonly": True}}

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            AppointmentMetaData,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    @action(
        "redact_generated_message",
        "Redact message and re-edit encounter",
        "This will replace the message sent to the user with “This message has been removed” and require practitioner to re-submit the encounter summary.",
    )
    def redact_message(self, appointment_metadata_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        current_user = login.current_user
        mpractice_admin_message_redaction_enabled = feature_flags.bool_variation(
            "enable-mpractice-admin-message-redaction",
            user_context(current_user),
            default=False,
        )
        if not mpractice_admin_message_redaction_enabled:
            log.warning(
                "Attempt to redact message by user not in test group",
                appointment_metadata_ids=appointment_metadata_ids,
            )
            abort(
                400,
                "This user is not configured for access to this feature in LaunchDarkly.",
            )

        if len(appointment_metadata_ids) != 1:
            log.warning(
                "Too many notes submitted for message redaction",
                appointment_metadata_ids=appointment_metadata_ids,
            )
            abort(
                400, "Bulk redaction is not allowed. Please redact one note at a time."
            )

        try:
            appointment_note = (
                db.session.query(AppointmentMetaData)
                .filter(AppointmentMetaData.id == appointment_metadata_ids[0])
                .one()
            )
        except NoResultFound:
            log.error(
                "ADMIN appointment metadata generated message redaction - "
                "Selected appointment metadata doesn't exist",
                appointment_metadata_ids=[appointment_metadata_ids[0]],
            )
            abort(
                400,
                f"Note {appointment_metadata_ids[0]} does not exist.",
            )

        if appointment_note.appointment_id is None:
            log.error(
                "ADMIN appointment metadata generated message redaction - "
                "Selected appointment metadata is not associated with an appointment",
                appointment_metadata_ids=[appointment_metadata_ids[0]],
            )
            abort(
                400,
                f"Note {appointment_metadata_ids[0]} does not have an appointment id.",
            )

        all_appointment_metadata = (
            db.session.query(AppointmentMetaData)
            .filter(
                AppointmentMetaData.appointment_id == appointment_note.appointment_id
            )
            .all()
        )

        all_structured_notes = (
            db.session.query(RecordedAnswerSet)
            .join(Questionnaire)
            .filter(RecordedAnswerSet.appointment_id == appointment_note.appointment_id)
            .filter(~Questionnaire.roles.any(Role.name == ROLES.member))
            .all()
        )

        all_generated_messages = (
            db.session.query(Message)
            .filter(Message.id.in_([a.message_id for a in all_appointment_metadata]))
            .all()
        )

        redacted_note_text = "This message has been removed."

        for generated_message in all_generated_messages:
            generated_message.body = redacted_note_text
            db.session.add(generated_message)

        for appointment_metadata in all_appointment_metadata:
            appointment_metadata.content = redacted_note_text
            appointment_metadata.draft = True
            db.session.add(appointment_metadata)

        for structured_note in all_structured_notes:
            structured_note.draft = True
            db.session.add(structured_note)

        db.session.commit()

        increment(
            metric_name="api.models.appointment_metadata.message_redacted",
            pod_name=PodNames.MPRACTICE_CORE,
        )

        flash(
            "Post session note and message have been redacted, structured note is set to draft status",
            "success",
        )


class PractitionerAckView(MavenAuditedView):
    read_permission = "read:practitioner-appointment-ack"
    delete_permission = "delete:practitioner-appointment-ack"
    create_permission = "create:practitioner-appointment-ack"
    edit_permission = "edit:practitioner-appointment-ack"

    column_filters = (
        "appointment.id",
        PhoneNumberFilter(PractitionerAppointmentAck.phone_number, "Phone Number"),
        "is_acked",
    )
    column_exclude_list = ["modified_at", "warn_by", "is_warned", "is_alerted"]

    form_rules = ["ack_by", "is_acked", "phone_number"]
    form_excluded_columns = [
        "modified_at",
        "created_at",
        "appointment",
        "warn_by",
        "is_warned",
        "is_alerted",
    ]

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            PractitionerAppointmentAck,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class AvailabilityNotificationPractitionerEmailFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(
            User, AvailabilityNotificationRequest.practitioner_id == User.id
        ).filter(User.email == value)


class AvailabilityNotificationMemberEmailFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(
            User, AvailabilityNotificationRequest.member_id == User.id
        ).filter(User.email == value)


class AvailabilityNotificationView(MavenAuditedView):
    read_permission = "read:availability-notification-request"
    edit_permission = "edit:availability-notification-request"
    column_list = (
        "member.full_name",
        "member.email",
        "practitioner.full_name",
        "practitioner.email",
        "modified_at",
        "created_at",
        "notified_at",
        "cancelled_at",
    )
    column_filters = (
        "id",
        "practitioner_id",
        "member_id",
        AvailabilityNotificationPractitionerEmailFilter(None, "Practitioner Email"),
        AvailabilityNotificationMemberEmailFilter(None, "Member Email"),
    )

    can_view_details = False

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            AvailabilityNotificationRequest,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ScheduledMaintenanceView(MavenAuditedView):
    create_permission = "create:scheduled-maintenance"
    edit_permission = "edit:scheduled-maintenance"
    delete_permission = "delete:scheduled-maintenance"
    read_permission = "read:scheduled-maintenance"

    column_filters = ("scheduled_start", "scheduled_end")
    form_excluded_columns = ("modified_at", "created_at")
    form_create_rules = [rules.Field("scheduled_start"), rules.Field("scheduled_end")]

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # if end date before start date or end date in the past, flag them invalid
        if (
            form.scheduled_end.data <= form.scheduled_start.data
            or form.scheduled_end.data <= datetime.datetime.utcnow()
        ):
            raise validators.ValidationError("Invalid schedule start and end time!")
        else:
            super().on_model_change(form, model, is_created)

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            ScheduledMaintenance,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
