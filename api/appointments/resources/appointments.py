import datetime
import hashlib

import stripe
from ddtrace import tracer
from flask import request
from flask_restful import abort
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound

from appointments.models.appointment import Appointment
from appointments.models.constants import PRIVACY_CHOICES
from appointments.models.needs_and_categories import Need
from appointments.models.schedule_event import ScheduleEvent
from appointments.repository.appointment import AppointmentRepository
from appointments.schemas.appointments_v3 import (
    AppointmentCreateSchemaV3,
    AppointmentGetSchemaV3,
    AppointmentSchemaV3,
    AppointmentsSchemaV3,
    MinimalAppointmentsSchemaV3,
)
from appointments.services.common import (
    can_member_book,
    check_intro_appointment_purpose,
    get_platform,
)
from appointments.services.schedule import (
    BookingConflictException,
    managed_appointment_booking_availability,
    validate_member_schedule,
)
from appointments.tasks.appointment_notifications import (
    confirm_booking_email_to_member,
    notify_about_new_appointment,
    schedule_member_appointment_confirmation,
)
from appointments.tasks.appointments import appointment_post_creation
from appointments.tasks.availability import update_practitioners_next_availability
from appointments.tasks.credits import refill_credits_for_enterprise_member
from appointments.utils.flask_redis_ext import (
    APPOINTMENT_REDIS,
    cache_response,
    invalidate_cache,
)
from appointments.utils.redis_util import invalidate_cache as invalidate
from authz.services.permission import add_appointment, only_member_or_practitioner
from common import stats
from common.services import ratelimiting
from common.services.api import AuthenticatedResource
from models.products import Product
from provider_matching.services.matching_engine import calculate_state_match_type
from services.common import calculate_privilege_type
from storage.connection import db
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from utils.service_owner_mapper import service_ns_team_mapper
from views.schemas.base import PaginableOutputSchemaV3

log = logger(__name__)


class AppointmentsResource(AuthenticatedResource):
    def redis_cache_key(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        query_params = "&".join(f"{k}={v}" for k, v in sorted(request.args.items()))
        user_id = self.user.id
        log.info(f"Redis cache key raw: appointment:{user_id}:{query_params}")
        return f"appointment:{user_id}:{hashlib.md5(query_params.encode('utf-8')).hexdigest()}"

    def redis_tags(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return [f"user_appointments:{self.user.id}"]

    def experiment_enabled(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return marshmallow_experiment_enabled(
            "experiment-enable-appointments-redis-cache",
            self.user.esp_id,
            self.user.email,
            default=False,
        )

    @cache_response(redis_name=APPOINTMENT_REDIS, namespace="appointments")
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # launch darkly flag
        args = self._check_get_args()
        user_id = self.user.id
        args["current_user_id"] = user_id

        member = None
        if "member_id" in args and args["member_id"]:
            member = validate_member_schedule(args["member_id"])

        (pagination, result) = AppointmentRepository(
            session=db.session
        ).get_appointments_paginated(args, member=member)
        del args["limit"]
        del args["offset"]

        schema: PaginableOutputSchemaV3

        if args.get("minimal"):
            schema = MinimalAppointmentsSchemaV3()
        else:
            schema = AppointmentsSchemaV3()

        schema.context["user_id"] = user_id  # type: ignore[attr-defined]
        schema.context["user"] = self.user  # type: ignore[attr-defined]
        data = {
            "data": only_member_or_practitioner(self.user, result),
            "meta": args,
            "pagination": pagination,
        }
        return schema.dump(data)  # type: ignore[attr-defined]

    @ratelimiting.ratelimited(attempts=5, cooldown=60)
    @add_appointment.require()
    @invalidate_cache(redis_name=APPOINTMENT_REDIS, namespace="appointments")
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self.init_timer()

        metric_name = (
            "api.appointments.resources.appointments.appointments_resource.post"
        )

        schema = AppointmentCreateSchemaV3()
        request_json = request.json if request.is_json else None

        args = schema.load(request_json or request.form)

        try:
            product = (
                db.session.query(Product)
                .filter(Product.id == args["product_id"])
                .options(
                    joinedload(Product.practitioner).joinedload("practitioner_profile"),
                    joinedload(Product.practitioner)
                    .joinedload("practitioner_profile")
                    .selectinload("certified_states"),
                    joinedload(Product.practitioner)
                    .joinedload("practitioner_profile")
                    .joinedload("certifications"),
                )
                .one()
            )
        except NoResultFound:
            abort(400, message="That product does not exist!")

        if not can_member_book(self.user, product):

            stats.increment(
                metric_name="api.appointments.resources.appointments.post",
                pod_name=stats.PodNames.CARE_DISCOVERY,
                tags=["reason:member_cannot_book_with_practitioner"],
            )
            abort(
                400,
                message="Doula member is not allowed to book with a non-doula provider",
            )

        scheduled_start = args["scheduled_start"]
        scheduled_end = scheduled_start + datetime.timedelta(minutes=product.minutes)
        provider_id = product.user_id
        product_id = product.id
        log.info(
            "Member booking appointment with practitioner",
            user_id=self.user.id,
            product_id=product_id,
            practitioner_id=provider_id,
            scheduled_start=str(scheduled_start),
            scheduled_end=str(scheduled_end),
        )
        self._safety_checks(args, scheduled_start, scheduled_end, product)
        appointment_purpose = check_intro_appointment_purpose(self.user, product)
        self.timer("safety_checks")
        need = None
        if need_id := args.get("need_id"):
            try:
                need = db.session.query(Need).filter(Need.id == need_id).one()
                need_name = None
                if need:
                    need_name = need.name
                log.info("Creating appointment with need", need_name=need_name)
            except NoResultFound:
                log.warning(
                    "need_id not found when creating appointment", need_id=need_id
                )

        try:
            with managed_appointment_booking_availability(
                product=product, scheduled_start=scheduled_start, member=self.user
            ):
                self.timer("product_availability")
                cancellation_policy = (
                    product.practitioner.practitioner_profile.default_cancellation_policy
                )
                if not cancellation_policy:
                    stats.increment(
                        metric_name=metric_name,
                        tags=[
                            "error:true",
                            "error_cause:missing_cancellation_policy",
                        ],
                        pod_name=stats.PodNames.CARE_DISCOVERY,
                    )
                    abort(400, message="No cancellation policy for that practitioner.")

                try:
                    event = ScheduleEvent.get_schedule_event_from_timestamp(
                        product.practitioner.schedule,
                        scheduled_start,
                    )
                except Exception as error:
                    abort(400, message=str(error))

                client_notes = args.get("pre_session", {}).get("notes") or None

                privacy = args.get("privacy", PRIVACY_CHOICES.basic)
                if privacy != PRIVACY_CHOICES.basic:
                    log.warning(
                        f"Unexpected privacy value received in POST appointments endpoint: {privacy}"
                    )

                appointment = Appointment(
                    schedule_event=event,
                    scheduled_start=scheduled_start,
                    scheduled_end=scheduled_end,
                    product=product,
                    purpose=appointment_purpose
                    or (product.purpose and product.purpose.value),
                    member_schedule=self.user.schedule,
                    cancellation_policy=cancellation_policy,
                    client_notes=client_notes,
                    privacy=privacy,
                    privilege_type=calculate_privilege_type(
                        product.practitioner, self.user
                    ),
                    state_match_type=calculate_state_match_type(
                        product.practitioner.practitioner_profile, self.user
                    ),
                    need=need,
                )

                user_agent = request.headers.get("User-Agent")
                appointment.json["platforms"] = {
                    "booked": get_platform(user_agent),
                    "booked_raw": user_agent,
                }
                payment = None
                # Moves the appointment from a transient state to a persistent state
                # to have the database identity (i.e. the appointment id)
                db.session.flush()
                appointment_id = appointment.id
                # invalidate for the practitioner side view
                invalidate(tags=[f"user_appointments:{appointment.practitioner_id}"])

                # This is to prevent enterprise users from running out of credits
                # in the future
                service_ns_tag = "appointments"
                team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
                refill_credits_for_enterprise_member.delay(
                    member_id=self.user.id,
                    appointment_id=appointment_id,
                    service_ns=service_ns_tag,
                    team_ns=team_ns_tag,
                )

                log.info(
                    "Created appointment for member",
                    appointment_id=appointment_id,
                    user_id=self.user.id,
                    practitioner_id=product.practitioner.id,
                    scheduled_start=str(scheduled_start),
                    scheduled_end=str(scheduled_end),
                )
                try:
                    payment = appointment.authorize_payment()
                except stripe.error.CardError as e:
                    log.info(
                        "Stripe Card Error",
                        error=str(e),
                        appointment_id=appointment_id,
                        product_id=product.id,
                        member_id=self.user.id,
                    )
                    stats.increment(
                        metric_name=metric_name,
                        tags=["error:true", "error_cause:invalid_payment"],
                        pod_name=stats.PodNames.CARE_DISCOVERY,
                    )
                    abort(400, message="Your credit card was declined...")
                except stripe.error.StripeError as e:
                    log.info(
                        "Generic Stripe Error",
                        error=str(e),
                        appointment_id=appointment_id,
                        product_id=product.id,
                        member_id=self.user.id,
                    )
                    stats.increment(
                        metric_name=metric_name,
                        tags=["error:true", "error_cause:generic_stripe_error"],
                        pod_name=stats.PodNames.CARE_DISCOVERY,
                    )
                    abort(400, message="Problem with stripe, try again.")

                self.timer("auth_payment")

                if payment:
                    log.info(
                        "Payment found for appointment",
                        appointment_id=appointment_id,
                    )
                    db.session.add(appointment)
                    db.session.commit()
                    self.timer("appointment commit")

                    service_ns_tag = "appointments"
                    team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
                    service_ns_tag_notifications = "appointment_notifications"
                    team_ns_tag_notifications = service_ns_team_mapper.get(
                        service_ns_tag_notifications
                    )

                    appointment_post_creation.delay(
                        appointment_id,
                        service_ns=service_ns_tag,
                        team_ns=team_ns_tag,
                    )
                    self.timer("delay appointment_post_creation")
                    notify_about_new_appointment.delay(
                        appointment_id,
                        service_ns=service_ns_tag_notifications,
                        team_ns=team_ns_tag_notifications,
                    )
                    self.timer("delay notify_about_new_appointment")

                    confirm_booking_email_to_member.delay(
                        appointment_id,
                        service_ns=service_ns_tag,
                        team_ns=team_ns_tag,
                    )
                    self.timer("delay confirm_booking_email_to_member")

                    schedule_member_appointment_confirmation.delay(
                        appointment_id,
                        service_ns=service_ns_tag,
                        team_ns=team_ns_tag,
                    )
                    self.timer("delay_tasks")

                    update_practitioners_next_availability([product.practitioner.id])
                    self.timer("next_avail_update")

                    res_schema = AppointmentSchemaV3()
                    res_schema.context["user"] = self.user  # type: ignore[attr-defined]
                    res = res_schema.dump(appointment)  # type: ignore[attr-defined]

                    self.timer("schema_dumped")
                    stats.increment(
                        metric_name=metric_name,
                        pod_name=stats.PodNames.CARE_DISCOVERY,
                        tags=["success:true"],
                    )
                    return res, 201
                else:
                    log.info(
                        "Payment NOT found for appointment",
                        appointment_id=appointment_id,
                    )
                    if self.user.is_enterprise:
                        log.info(
                            "Payment NOT found for the enterprise user for appointment",
                            appointment_id=appointment_id,
                        )
                        stats.increment(
                            metric_name=metric_name,
                            pod_name=stats.PodNames.CARE_DISCOVERY,
                            tags=[
                                "error:true",
                                "error_cause:payment_authorization_failure",
                                "variant:enterprise_user",
                            ],
                        )
                    self.audit(
                        "appointment_create_failure",
                        product=product.id,
                        start_time=str(scheduled_start),
                        member_id=self.user.id,
                    )
                    db.session.rollback()
                    self.timer("rollback")
                    stats.increment(
                        metric_name=metric_name,
                        pod_name=stats.PodNames.CARE_DISCOVERY,
                        tags=[
                            "error:true",
                            "error_cause:payment_authorization_failure",
                            "variant:overall",
                        ],
                    )
                    abort(400, message="Could not authorize payment!")
        except BookingConflictException:
            self.timer("bad_time")
            stats.increment(
                metric_name=metric_name,
                pod_name=stats.PodNames.CARE_DISCOVERY,
                tags=["error:true", "error_cause:invalid_time"],
            )
            log.error(
                "Post appointments: Invalid time",
                user_id=self.user.id,
                practitioner_id=provider_id,
                scheduled_start=str(scheduled_start),
                scheduled_end=str(scheduled_end),
            )
            abort(
                400,
                message=(
                    "That start time is unavailable! Most likely "
                    "there is a booking conflict."
                ),
            )

    @tracer.wrap()
    def _safety_checks(self, args, scheduled_start, scheduled_end, product):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        metric_name = (
            "appointments.resources.appointments.appointments_resource.safety_checks"
        )
        now = datetime.datetime.utcnow()
        if scheduled_start < now:
            stats.increment(
                metric_name=metric_name,
                pod_name=stats.PodNames.CARE_DISCOVERY,
                tags=["error:true", "error_cause:incorrect_appointment_start_time"],
            )
            abort(400, message="Cannot schedule an appointment in the past!")
        if scheduled_end > (now + datetime.timedelta(days=7)):
            if scheduled_end < (now + datetime.timedelta(days=30)):
                stats.increment(
                    metric_name=metric_name,
                    pod_name=stats.PodNames.CARE_DISCOVERY,
                    tags=["error:false", "message:booking_beyond_7_days"],
                )
            else:
                stats.increment(
                    metric_name=metric_name,
                    pod_name=stats.PodNames.CARE_DISCOVERY,
                    tags=["error:true", "error_cause:incorrect_appointment_start_time"],
                )
                abort(400, message="Cannot currently schedule an appt > 7 days!")
        if self.user == product.practitioner:
            stats.increment(
                metric_name=metric_name,
                pod_name=stats.PodNames.CARE_DISCOVERY,
                tags=["error:true", "error_cause:practitioner_is_member"],
            )
            abort(400, message="Cannot book with yourself!")
        if not self.user.schedule:
            stats.increment(
                metric_name=metric_name,
                pod_name=stats.PodNames.CARE_DISCOVERY,
                tags=["error:true", "error_cause:no_member_schedule"],
            )
            abort(
                400,
                message="You do not have a schedule, please try again in "
                "a minute - if you have continued trouble please contact "
                "support@mavenclinic.com",
            )
        if product.practitioner.is_care_coordinator:
            care_team_ids = [ct.user_id for ct in self.user.care_team]
            if product.practitioner.id not in care_team_ids:
                log.warning(
                    "Appointment being booked with care coordinator not in care team",
                    user_id=self.user.id,
                    practitioner_id=product.practitioner.id,
                    care_team=care_team_ids,
                )

        profile = product.practitioner.practitioner_profile

        min_time = datetime.datetime.utcnow() + datetime.timedelta(
            minutes=profile.booking_buffer
        )
        if scheduled_start <= min_time:
            stats.increment(
                metric_name=metric_name,
                pod_name=stats.PodNames.CARE_DISCOVERY,
                tags=["error:true", "error_cause:booking_buffer_overlap"],
            )
            log.error(
                "_safety_checks(): booking buffer overlap",
                user_id=self.user.id,
                practitioner_id=product.user_id,
                scheduled_start=str(scheduled_start),
                scheduled_end=str(scheduled_end),
                min_time=min_time,
            )
            abort(400, message="Please choose a later start time!")

    def _check_get_args(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema = AppointmentGetSchemaV3()
        args = schema.load(request.args)

        if args.get("practitioner_id") and (args["practitioner_id"] != self.user.id):
            abort(403)
        elif args.get("member_id") and (args["member_id"] != self.user.id):
            # allow practitioners to filter to a given member ID
            if not args.get("practitioner_id"):
                abort(403)

        if not any([args.get("member_id"), args.get("practitioner_id")]):
            if self.user.practitioner_profile:
                args["practitioner_id"] = self.user.id
            else:
                args["member_id"] = self.user.id

        if (
            args.get("scheduled_start")
            or request.args.get("scheduled_start_before")
            or args.get("scheduled_end")
        ) and not (
            args.get("schedule_event_ids")
            or all([args.get("scheduled_start"), args.get("scheduled_end")])
            or all(
                [request.args.get("scheduled_start_before"), args.get("scheduled_end")]
            )
        ):
            abort(400, message="Both start and end required!")

        return args
