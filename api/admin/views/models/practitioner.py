from __future__ import annotations

import csv
import datetime
import io
import json
import re
from typing import Type

import flask_login as login
from flask import Response, flash, request, url_for
from flask_admin import BaseView, expose
from flask_admin.form import rules
from flask_admin.model.helpers import get_mdict_item_or_list
from marshmallow import Schema
from marshmallow import fields as marsh_fields
from werkzeug.utils import redirect
from wtforms import fields

from admin.common import https_url
from admin.views.auth import AdminAuth
from admin.views.base import (
    AdminCategory,
    AdminViewT,
    AuthenticatedMenuLink,
    MavenAuditedView,
    ViewExtras,
)
from appointments.models.appointment import Appointment
from appointments.models.schedule_event import ScheduleEvent
from appointments.schemas.appointments import (
    MinimalAdminAppointmentSchema,
    PotentialAppointmentSchema,
    ScheduleEventSchema,
)
from appointments.utils.booking import AvailabilityCalculator, AvailabilityTools
from audit_log.utils import emit_audit_log_read, emit_bulk_audit_log_update
from authn.models.user import User
from care_advocates.models.transitions import CareAdvocateMemberTransitionTemplate
from care_advocates.services.transition_log import (
    CareAdvocateMemberTransitionLogService,
    IncorrectTransitionLogIDError,
    SubmittingTransitionLogErrors,
    TransitionLogError,
)
from care_advocates.services.transition_template import (
    CareAdvocateMemberTransitionTemplateService,
)
from common import stats
from models.products import Product
from models.profiles import (
    CareTeamTypes,
    MemberPractitionerAssociation,
    PractitionerProfile,
)
from models.verticals_and_specialties import Specialty, Vertical
from provider_matching.services.matching_engine import (
    StateMatchNotPermissibleError,
    state_match_not_permissible,
)
from storage.connection import db
from storage.connector import RoutingSQLAlchemy
from utils.log import logger

log = logger(__name__)


def json_converter(o):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if isinstance(o, datetime.datetime):
        return o.__str__()


class PractitionerAvailabilityView:
    @expose("/bookable_times/")
    def bookable_times_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        id_ = request.args.get("id")

        availability_start_time = request.args.get("start_date")
        if not id_:
            return (
                {"error": "`id` query parameter is required to retrieve availability."},
                400,
            )

        product_id = request.args.get("product_id")
        days = request.args.get(
            "days", PractitionerHelpers.BOOKABLE_TIMES_MIN_DAYS, int
        )

        if (
            days < PractitionerHelpers.BOOKABLE_TIMES_MIN_DAYS
            or days > PractitionerHelpers.BOOKABLE_TIMES_MAX_DAYS
        ):
            return json.dumps(
                {
                    "error": f"Please enter a time span between {PractitionerHelpers.BOOKABLE_TIMES_MIN_DAYS} and {PractitionerHelpers.BOOKABLE_TIMES_MAX_DAYS} days"
                },
                default=json_converter,
            )

        model = self.get_one(id_)  # type: ignore[attr-defined] # "PractitionerAvailabilityView" has no attribute "get_one"
        product = Product.query.filter(Product.id == product_id).one()

        bookable_appointment_times = PractitionerHelpers.get_bookable_times(
            model=model,
            product=product,
            days=days,
            availability_start_time=availability_start_time,
            check_daily_intro_capacity=False,
        )
        availability = PractitionerHelpers.get_availability(model)
        appointments = PractitionerHelpers.get_appointments(model)
        past_appointments = PractitionerHelpers.get_past_appointments(model)

        appointment_schema = MinimalAdminAppointmentSchema(many=True)
        appointment_schema.context["admin"] = True
        availability_schema = ScheduleEventSchema(many=True)
        potential_appointment_schema = PotentialAppointmentSchema(many=True)

        emit_audit_log_read(model)
        return {
            "available_times": potential_appointment_schema.dump(
                bookable_appointment_times
            ).data,
            "scheduled_availability": availability_schema.dump(availability).data,
            "upcoming_appointments": appointment_schema.dump(appointments).data,
            "past_appointments": appointment_schema.dump(past_appointments).data,
        }

    @expose("/products/", methods=["GET"])
    def get_product_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        product_id = get_mdict_item_or_list(request.args, "product_id")

        if product_id:
            products = Product.query.filter(Product.id == product_id)

            if products.count() > 0:
                product = products.one()
                verticals = Vertical.query.filter(Vertical.id == product.vertical_id)
                vertical = verticals.one() if verticals.count() > 0 else None

                response = {}
                response["practitioner_name"] = product.practitioner.full_name
                response["practitioner_id"] = product.practitioner.id

                response["certified_states"] = [
                    certified_state.abbreviation
                    for certified_state in product.practitioner.practitioner_profile.certified_states
                ]

                response["product_id"] = product.id
                response["minutes"] = product.minutes
                response[
                    "anonymous_allowed"
                ] = product.practitioner.practitioner_profile.anonymous_allowed

                response["vertical"] = {}
                response["vertical"]["name"] = vertical.name if vertical else None

                response["vertical"]["filter_by_state"] = (
                    vertical.filter_by_state if vertical else None
                )
                response["vertical"]["in_state_matching_states"] = (
                    [
                        in_state.abbreviation
                        for in_state in vertical.in_state_matching_states
                    ]
                    if vertical
                    else None
                )
                emit_audit_log_read(product)
                return json.dumps(response, default=json_converter)
            else:
                return json.dumps(False, default=json_converter)

    @expose("/state-match-not-permissible/", methods=["GET"])
    def get_state_match_not_permissible(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        product_id = request.args.get("product_id")
        user_id = request.args.get("user_id")

        if not user_id:
            return (
                {"error": "No user_id in request"},
                400,
            )

        if not product_id:
            return (
                {"error": "No product id in request"},
                400,
            )

        product = Product.query.get(product_id)
        if product:
            emit_audit_log_read(product)
        if not product:
            return ({"error": "product not found"}, 400)

        user = User.query.get(user_id)
        if user:
            emit_audit_log_read(user)
        practitioner_profile = (
            product.practitioner.practitioner_profile if product.practitioner else None
        )

        if not practitioner_profile:
            return (
                {"error": "practitioner not found"},
                400,
            )

        if not user:
            return (
                {"error": "user not found"},
                400,
            )

        user_state = (
            user.member_profile.state.abbreviation
            if user.member_profile.state
            else None
        )

        # If provider is in list of previously met providers, bypass state matching
        user_care_team = (
            MemberPractitionerAssociation.query.filter_by(
                user_id=user_id,
                type=CareTeamTypes.APPOINTMENT,
            )
        ).all()

        care_team_practitioner_ids = [
            care_team.practitioner_id for care_team in user_care_team
        ]

        if practitioner_profile.user_id in care_team_practitioner_ids:
            return json.dumps(
                {
                    "practitioner_id": practitioner_profile.user_id,
                    "certified_states": [
                        s.abbreviation for s in practitioner_profile.certified_states
                    ],
                    "user_id": user.id,
                    "user_state": user_state,
                    "state_match_not_permissible": False,
                }
            )

        try:
            bad_state_match = state_match_not_permissible(
                practitioner_profile, user, product
            )
        except StateMatchNotPermissibleError as e:
            return (
                {"error": str(e)},
                400,
            )
        if bad_state_match and (
            f"/admin/memberprofile/edit/?id={user_id}&url=%2Fadmin%2Fmemberprofile%2F"
            in request.environ.get("HTTP_REFERER", "")
        ):  # track when this shows the out-of-state error for proactive booking on the member profile
            vertical_name = product.vertical.name if product.vertical else "None"
            log.info(
                "Proactive Booking - state match not permissible error text",
                practitioner_id=practitioner_profile.user_id,
                user_id=user_id,
                user_state=user_state,
                http_referer=request.environ.get("HTTP_REFERER"),
                vertical_name=vertical_name,
            )
            stats.increment(
                metric_name="admin.views.models.practitioner.state_match_not_permissible",
                pod_name=stats.PodNames.CARE_DISCOVERY,
                tags=[
                    f"practitioner_id:{practitioner_profile.user_id}",
                    f"user_state:{user_state}",
                    f"vertical:{vertical_name}",
                ],
            )

        return json.dumps(
            {
                "practitioner_id": practitioner_profile.user_id,
                "certified_states": [
                    s.abbreviation for s in practitioner_profile.certified_states
                ],
                "user_id": user.id,
                "user_state": user_state,
                "state_match_not_permissible": bad_state_match,
            }
        )


class PractitionerHelpers:
    BOOKABLE_TIMES_MIN_DAYS = 28
    BOOKABLE_TIMES_MAX_DAYS = 84

    # return 12 weeks of availability
    @staticmethod
    def get_bookable_times(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        model,
        product,
        days,
        availability_start_time=None,
        check_daily_intro_capacity=True,
    ):
        if not availability_start_time:
            availability_start_time = datetime.datetime.utcnow()
        else:
            availability_start_time = datetime.datetime.fromisoformat(
                availability_start_time
            )

        start_time = AvailabilityTools.pad_and_round_availability_start_time(
            availability_start_time,
            model.user.practitioner_profile.booking_buffer,
            model.user.practitioner_profile.rounding_minutes,
        )
        end_time = start_time + datetime.timedelta(days=days)

        """
        Move the end time to the end of the day to make sure we're including
        all bookable times for that day.
        """
        end_time = datetime.datetime.combine(end_time, datetime.time.max)

        calculator = AvailabilityCalculator(
            practitioner_profile=model.user.practitioner_profile, product=product
        )

        bookable_times = calculator.get_availability(
            start_time=start_time,
            end_time=end_time,
            check_daily_intro_capacity=check_daily_intro_capacity,
        )

        bookable_times.sort(key=lambda t: t.scheduled_start)
        return bookable_times

    @staticmethod
    def get_availability(model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            db.session.query(ScheduleEvent)
            .filter(
                ScheduleEvent.ends_at >= datetime.datetime.utcnow(),
                ScheduleEvent.schedule_id == model.user.schedule.id,
            )
            .order_by(ScheduleEvent.starts_at)
            .all()
        )

    @staticmethod
    def get_active_products(model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            db.session.query(Product)
            .filter(Product.practitioner == model.user, Product.is_active == True)
            .all()
        )

    @staticmethod
    def get_appointments(model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            db.session.query(Appointment)
            .join(Product)
            .filter(
                Product.practitioner == model.user,
                Appointment.scheduled_start >= datetime.datetime.utcnow(),
            )
            .order_by(Appointment.scheduled_start)
            .all()
        )

    @staticmethod
    def get_past_appointments(model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        now = datetime.datetime.utcnow()
        return (
            db.session.query(Appointment)
            .join(Product)
            .filter(
                Product.practitioner == model.user,
                Appointment.scheduled_start < now,
                Appointment.scheduled_start >= now - datetime.timedelta(hours=72),
            )
            .order_by(Appointment.scheduled_start.desc())
            .all()
        )


class PractitionerReplacementView(AdminAuth, BaseView, ViewExtras):
    read_permission = "read:replace-prac-in-care-team"
    delete_permission = "delete:replace-prac-in-care-team"
    create_permission = "create:replace-prac-in-care-team"
    edit_permission = "edit:replace-prac-in-care-team"

    @expose("/")
    def index(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))
        return self.render("practitioner_replacement.html")


class TransitionLogSchema(Schema):
    id = marsh_fields.Integer(required=True)
    user_id = marsh_fields.Integer(required=True)
    date_scheduled = marsh_fields.DateTime(required=True)
    uploaded_filename = marsh_fields.String(required=True)
    uploaded_content = marsh_fields.String(required=True)


class CAMemberTransitionsView(AdminAuth, BaseView, ViewExtras):
    read_permission = "read:ca-member-transition"
    delete_permission = "delete:ca-member-transition"
    create_permission = "create:ca-member-transition"
    edit_permission = "edit:ca-member-transition"

    # Define view properties
    transition_logs_columns_conf = [
        {"id": "id", "label": "ID"},
        {"id": "user_id", "label": "User ID"},
        {"id": "user_name", "label": "User Name"},
        {
            "id": "date_uploaded",
            "label": "Date Uploaded",
            "formatterType": "dateWithTimezone",
            "sort": "created_at",
        },
        {
            "id": "date_of_transition",
            "label": "Date of Transition",
            "formatterType": "dateWithTimezone",
            "sort": "date_transition",
        },
        {"id": "uploaded_file", "label": "Uploaded File"},
    ]
    transition_templates_columns_conf = [
        {"id": "id", "label": "ID"},
        {"id": "message_type", "label": "Message Type"},
        {"id": "message_description", "label": "Message Description"},
        {"id": "message_body", "label": "Message Body Preview"},
    ]

    index_view_delete_conf = {
        "deleteFormUrl": "/admin/ca_member_transitions/transition_logs/delete",
        "hiddenUrl": "/admin/ca_member_transitions/",
    }

    index_view_args = {
        "show_tz": "false",
        "show_pagination": "false",
        "transition_logs_can_delete": "true",
        "transition_logs_can_edit": "false",
        "transition_templates_can_delete": "false",
        "transition_templates_can_edit": "true",
        "page_size": 10,
        "transition_logs_columns_conf": transition_logs_columns_conf,
        "transition_templates_columns_conf": transition_templates_columns_conf,
        "delete_conf": index_view_delete_conf,
    }

    @expose("/")
    def index(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))

        # Get transition logs sort column
        self.index_view_args["tl_sort_c"] = request.args.get("sort")

        return self.render("ca_member_transitions.html", view_args=self.index_view_args)

    @expose("/transition_logs")
    def get_list_transition_logs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        sort_column = request.args.get("sort")
        if sort_column is None:
            sort_column = "date_transition"

        transition_logs_data = (
            CareAdvocateMemberTransitionLogService().get_transition_logs_data(
                sort_column=sort_column
            )
        )

        return {
            "data": {
                "items": transition_logs_data,
                "pagination": {
                    "limit": 10,
                    "total": len(transition_logs_data),
                },
            }
        }

    @expose("transition_logs/delete", methods=("POST",))
    def delete(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if "id" not in request.form:
            return_msg = "Transition log ID not passed in request form"
            log.info(return_msg)
            flash(return_msg)
            return redirect(https_url("ca_member_transitions.index"))

        transition_log_id = request.form.get("id")

        if not transition_log_id.isdigit():  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "isdigit"
            return_msg = "Transition log ID must be an integer"
            log.info(return_msg, transition_log_id=transition_log_id)
            flash(return_msg)
            return redirect(https_url("ca_member_transitions.index"))

        transition_log_id = int(transition_log_id)  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"

        try:
            CareAdvocateMemberTransitionLogService().delete_transition_log(
                id=transition_log_id,
            )
            return_msg = "CA-Member Transition Log deleted"

        # For all of the following errors (both client and server), we would like to return respective 400/500 status code.
        # Nonetheless, that won't be possible because it will imply that flask admin won't automatically redirect to our index view
        # We will then return a 302 and keep record of the errors with data dog
        except TransitionLogError as e:
            return_msg = str(e)

        flash(return_msg)
        return redirect(https_url("ca_member_transitions.index"), code=302)

    @expose("transition_logs/download_csv/<int:transition_log_id>")
    def download_csv(self, transition_log_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            (
                csv_content,
                csv_file_name,
            ) = CareAdvocateMemberTransitionLogService().download_transition_log_csv(
                id=transition_log_id
            )

            return Response(
                csv_content,
                mimetype="text/csv",
                headers={
                    "Content-disposition": f"attachment; filename={csv_file_name}"
                },
            )
        except IncorrectTransitionLogIDError as e:
            flash(str(e))
            return redirect(https_url("ca_member_transitions.index"), code=302)

    @expose("/transition_templates")
    def get_list_transition_templates(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        sort_column = request.args.get("sort")
        if sort_column is None:
            sort_column = "message_type"

        # _id_ will be replaced by each transition_template's id in construct_transition_templates_data()
        transition_templates_edit_url = url_for(
            "ca_member_transition_templates.edit_view", id="_id_"
        )

        transition_templates_data = (
            CareAdvocateMemberTransitionTemplateService().get_transition_templates_data(
                sort_column=sort_column,
                transition_templates_edit_url=transition_templates_edit_url,
            )
        )

        return {
            "data": {
                "items": transition_templates_data,
                "pagination": {
                    "limit": 10,
                    "total": len(transition_templates_data),
                },
            }
        }

    @expose("/submit", methods=("POST",))
    def submit_transition(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # Validate inputs
        user_id = login.current_user.id
        transitions_csv = request.files.get("transitions_csv")
        if not transitions_csv:
            return {
                "error": ["Please upload a file with your desired transitions."]
            }, 400

        transition_date_string = request.form.get("transition_date")
        if not transition_date_string:
            return {"error": ["Please specify a transition_date."]}, 400
        transition_date = datetime.datetime.strptime(
            transition_date_string, "%m/%d/%Y %I:%M %p"
        )
        current_time = datetime.datetime.now()
        # to account for lag between not passing seconds, submitting and validating,
        # as long as it was scheduled for the last few minutes, we will accept this
        current_time -= datetime.timedelta(minutes=2)
        if not transition_date or transition_date <= current_time:
            return {"error": ["Please provide a valid date for this transition."]}, 400

        # Call service layer to submit the transition log
        try:
            transition_log = (
                CareAdvocateMemberTransitionLogService().submit_transition_log(
                    user_id=user_id,
                    transition_date=transition_date,
                    transitions_csv=transitions_csv,
                )
            )

        except SubmittingTransitionLogErrors as e:
            return {"error": e.errors}, 400

        return_schema = TransitionLogSchema()
        return return_schema.dump(transition_log)


def _get_ca_member_transition_valid_fields_html():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    base_html = (
        '<div class="control-group">'
        '    <div class="control-label">'
        "        Valid fields:"
        "    </div>"
        '    <div class="controls">'
        "        <ul>"
    )
    for template_field in VALID_CA_MEMBER_TRANSITION_TEMPLATE_FIELDS:
        base_html += f"<li>{template_field}</li>"
    base_html += "</ul></div></div>"
    return base_html


VALID_CA_MEMBER_TRANSITION_TEMPLATE_FIELDS = [
    "$MEMBER_FIRST_NAME",
    "$OLD_CX_FIRST_NAME",
    "$NEW_CX_FIRST_NAME",
]


class CAMemberTransitionTemplateView(MavenAuditedView):
    form_overrides = {
        "message_body": fields.TextAreaField,
    }

    form_edit_rules = (
        "message_type",
        "message_description",
        "message_body",
        rules.Text(_get_ca_member_transition_valid_fields_html(), escape=False),
        "slug",
    )

    form_widget_args = {
        "message_type": {
            "readonly": True,
        },
        "message_body": {
            "readonly": True,
            "rows": 10,
            "cols": 10,
        },
        "slug": {"readonly": True},
    }

    column_descriptions = {
        "message_type": "<i>Submit JIRA ticket to update this field</i>",
        "message_body": "<i>Submit JIRA ticket to update this field</i>",
        "slug": "<i>Submit JIRA ticket to update this field</i>",
    }

    react_tab_param = "?tab=edit-messages"

    @expose("/")
    def index(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # We'll override the list view, since technically someone could manually navigate here.
        # We'll have it redirect to the ca_member_transitions page.
        return redirect(https_url("ca_member_transitions.index") + self.react_tab_param)

    def get_save_return_url(self, model, is_created=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # We want this flask admin page to redirect to the react page on save.
        return https_url("ca_member_transitions.index") + self.react_tab_param

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
            CareAdvocateMemberTransitionTemplate,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    def _validate_message_body(self, message_body):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        template_variables = re.findall(r"\$[a-zA-Z_]+", message_body)

        invalid_template_varaibles = set()
        for template_variable in template_variables:
            if template_variable not in VALID_CA_MEMBER_TRANSITION_TEMPLATE_FIELDS:
                invalid_template_varaibles.add(template_variable)

        return invalid_template_varaibles

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if getattr(  # noqa  B009  TODO:  Do not call getattr with a constant attribute value, it is not any safer than normal property access.
            form,
            "message_body",
        ):
            invalid_fields = self._validate_message_body(form.message_body.data)

            if invalid_fields:
                db.session.rollback()

                if len(invalid_fields) == 1:
                    invalid_fields_message = f"Invalid field: {invalid_fields.pop()}"
                else:
                    invalid_fields_message = (
                        f"Invalid fields: [{', '.join(invalid_fields)}]"
                    )
                flash(
                    invalid_fields_message,
                    "error",
                )
                return

        return super().validate_form(form)


class PractitionerSpecialtyBulkUpdateView(AdminAuth, BaseView, ViewExtras):
    read_permission = "upload:practitioner-specialty-bulk-update"
    delete_permission = "upload:practitioner-specialty-bulk-update"
    create_permission = "upload:practitioner-specialty-bulk-update"
    edit_permission = "upload:practitioner-specialty-bulk-update"

    @expose("/")
    def index(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.render("practitioner_specialty_bulk_update.html")

    @expose("/upload", methods=("POST",))
    def specialty_practitioner_bulk_update(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        This endpoint takes in a CSV with the headers: "Provider ID", and
        "Specialties". Provider ID should be an int and "Specialties" should
        be a comma-separated list of specialties.

        The given list of specialties will *replace* a provider's current
        specialties
        """
        provider_specialty_csv = request.files.get("specialty_csv")

        if not provider_specialty_csv:
            return {"error": "You need to upload a csv file."}, 400

        specialities_by_provider_id = {}
        success_ids = []
        errors = {}
        with io.StringIO(provider_specialty_csv.stream.read().decode()) as stream:
            reader = csv.DictReader(stream)
            if "Provider ID" not in reader.fieldnames:
                return {
                    "error": "Invalid csv file, file header should include 'Provider ID'"
                }, 400
            if "Specialties" not in reader.fieldnames:
                return {
                    "error": "Invalid csv file, file header should include 'Specialties'"
                }, 400

            for row in reader:
                try:
                    provider_id = int(row["Provider ID"])
                    specialties = {s.strip() for s in row["Specialties"].split(",")}
                except Exception:
                    errors.setdefault("invalid_row", [])
                    errors["invalid_row"].append(reader.line_num)
                    continue

                # If a duplicate is found, we will take the latest in the file
                if provider_id in specialities_by_provider_id:
                    errors.setdefault("duplicate_ids", [])
                    errors["duplicate_ids"].append(provider_id)

                specialities_by_provider_id[provider_id] = specialties

            try:
                db_providers: list[PractitionerProfile] = (
                    db.session.query(PractitionerProfile)
                    .filter(
                        PractitionerProfile.user_id.in_(
                            list(specialities_by_provider_id.keys())
                        )
                    )
                    .all()
                )
                db_providers_map = {p.user_id: p for p in db_providers}

                db_specialties: list[Specialty] = db.session.query(Specialty).all()
                db_specialty_map = {s.name: s for s in db_specialties}
                db_specialty_names = set(db_specialty_map.keys())

                # Validate that the given provider_id and specialties are in the database
                # then, update the provider to use the new specialties
                for provider_id, specialties in specialities_by_provider_id.items():
                    # Check if a provider id is in the database
                    if provider_id not in db_providers_map:
                        errors.setdefault("invalid_provider_ids", [])
                        errors["invalid_provider_ids"].append(provider_id)
                        continue

                    if invalid_specialties := specialties - db_specialty_names:
                        errors.setdefault("invalid_specialty_names", [])
                        err_msg = (
                            f"{invalid_specialties} for provider_id: {provider_id}"
                        )
                        errors["invalid_specialty_names"].append(err_msg)
                        continue

                    new_specialties = [db_specialty_map[s] for s in specialties]
                    db_provider = db_providers_map[provider_id]
                    db_provider.specialties = new_specialties
                    success_ids.append(provider_id)

            except Exception as e:
                log.error(e)
                db.session.rollback()
                return {"error": "Mysql error, rolling back"}, 400

            emit_bulk_audit_log_update(
                [p for p in db_providers if p.user_id in db_providers_map]
            )
            db.session.commit()

        return {
            "success_ids": success_ids,
            "errors": errors,
        }

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
            None,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class CareTeamControlCenterView(AuthenticatedMenuLink):
    read_permission = "read:care-team-control-center"
    delete_permission = "delete:care-team-control-center"
    create_permission = "create:care-team-control-center"
    edit_permission = "edit:care-team-control-center"

    required_capability = "admin_care_team_control_center"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")


class PractitionerToolsView(AuthenticatedMenuLink):
    read_permission = "read:practitioner-tools"
    delete_permission = "delete:practitioner-tools"
    create_permission = "create:practitioner-tools"
    edit_permission = "edit:practitioner-tools"

    required_capability = "admin_practitioner_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
