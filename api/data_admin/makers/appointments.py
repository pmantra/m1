import datetime
import math
import random

import dateparser
from flask import flash

from appointments.models.schedule import Schedule
from appointments.services.schedule import update_practitioner_profile_next_availability
from authn.models.user import User
from data_admin.data_factory import DataFactory
from data_admin.maker_base import _MakerBase
from data_admin.makers.organization import OrganizationMaker
from data_admin.makers.user import UserMaker
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class ScheduleEventMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        email = spec.get("practitioner")
        practitioner = User.query.filter_by(email=email).one_or_none()
        if not practitioner:
            flash(f"User not found: {email}", "error")
            return
        elif not practitioner.is_practitioner:
            flash(f"User <{email}> is not a practitioner!", "error")
            return

        if practitioner.schedule:
            schedule = practitioner.schedule
        else:
            log.debug("Adding schedule for %s", practitioner)
            schedule = Schedule(
                name=f"Schedule for {practitioner.full_name}", user=practitioner
            )
            db.session.add(schedule)
            db.session.flush()

        # todo refactor detect_schedule_conflict to reuse
        # detect_schedule_conflict(
        #     schedule, spec.get('starts_at'), spec.get('ends_at')
        # )

        starts_at = spec.get("starts_at")
        if not starts_at and spec.get("starts_in"):
            starts_at = dateparser.parse(spec.get("starts_in"))
        if not starts_at:
            flash("No starts_at!", "error")
            return

        ends_at = spec.get("ends_at")
        if not ends_at and spec.get("ends_in"):
            ends_at = dateparser.parse(spec.get("ends_in"))
        if not ends_at and spec.get("minutes"):
            ends_at = starts_at + datetime.timedelta(minutes=spec.get("minutes"))
        if not ends_at:
            flash("No ends_at!", "error")
            return

        se = DataFactory(None, "no client").add_and_return_event(
            schedule=schedule, starts_at=starts_at, ends_at=ends_at
        )
        update_practitioner_profile_next_availability(practitioner.practitioner_profile)
        return se


class AppointmentMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        practitioner = User.query.filter_by(
            email=spec.get("practitioner")
        ).one_or_none()
        if not practitioner:
            flash(f"Practitioner not found: {spec.get('practitioner')}", "error")
            return
        if not practitioner.products:
            flash(f"No products for {practitioner}", "error")
            return

        product_vertical = spec.get("product_vertical")
        product = None
        if product_vertical:
            for practitioner_product in practitioner.products:
                if practitioner_product.vertical.name == product_vertical:
                    product = practitioner_product
            if product is None:
                flash(
                    f"No product with vertical: {product_vertical} for practitioner: {practitioner}",
                    "error",
                )
                return
        else:
            product = sorted(practitioner.products, key=lambda x: x.minutes)[0]

        member = User.query.filter_by(email=spec.get("member")).one_or_none()
        if not member:
            flash(f"Member not found: {spec.get('member')}", "error")
            return
        if not member.schedule:
            flash(f"No schedule for {member}", "error")
            return
        member_schedule = member.schedule

        if spec.get("scheduled_start"):
            spec["scheduled_start"] = dateparser.parse(spec["scheduled_start"])
        elif spec.get("scheduled_start_in"):
            spec["scheduled_start"] = dateparser.parse(spec["scheduled_start_in"])
        else:
            flash("No scheduled_start!", "error")
            return

        if spec.get("member_started_at"):
            spec["member_started_at"] = dateparser.parse(spec["member_started_at"])
        if spec.get("member_ended_at"):
            spec["member_ended_at"] = dateparser.parse(spec["member_ended_at"])
        if spec.get("practitioner_started_at"):
            spec["practitioner_started_at"] = dateparser.parse(
                spec["practitioner_started_at"]
            )
        if spec.get("practitioner_ended_at"):
            spec["practitioner_ended_at"] = dateparser.parse(
                spec["practitioner_ended_at"]
            )

        if spec.get("cancelled_at"):
            spec["cancelled_at"] = dateparser.parse(spec["cancelled_at"])
            if spec["cancelled_at"] is not None:
                spec["cancelled_by_user_id"] = member.id

        allowed_args = (
            "created_at",
            "purpose",
            "cancelled_at",
            "scheduled_start",
            "member_started_at",
            "member_ended_at",
            "practitioner_started_at",
            "practitioner_ended_at",
            "cancelled_by_user_id",
        )
        kwargs = {k: spec[k] for k in allowed_args if k in spec}
        appt = DataFactory(None, "no client").add_appointment(
            product=product, member_schedule=member_schedule, **kwargs
        )
        return appt


class PooledCalendarMaxMaker(_MakerBase):
    """
    Create Pooled Calendar Max creates 3 CA's with maximum availability (a full
    pooled calendar's worth - every date/time available for the next week)
    and a member who is eligible to match with the CA's.
    """

    def create_object(self, spec_data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        result = []

        org_name = "Pooled Calendar Max Org"

        if (
            "restrict_to_new_organization" in spec_data
            and spec_data["restrict_to_new_organization"]
        ):

            org = {
                "type": "organization",
                "name": org_name,
                "activated_at": "1 minute ago",
            }
            organization = OrganizationMaker().create_object_and_flush(org)
            db.session.add(organization)
            result.append(organization)
            spec_data["organization_id"] = organization.id
        # Create 3 CAs with full availability for next 7 days
        datetime_now = datetime.datetime.now()
        # we want to round to the next 15-minute time slot so that the appointment times are "nice"
        nearest_time_interval = datetime.datetime.min + math.ceil(
            (datetime_now - datetime.datetime.min) / datetime.timedelta(minutes=15)
        ) * datetime.timedelta(minutes=15)
        for _ in range(3):
            ca = UserMaker().create_object_and_flush(spec_data)
            db.session.add(ca)
            result.append(ca)
            schedule_event = {
                "type": "schedule_event",
                "minutes": 7 * 24 * 60,
                "practitioner": ca.email,
                "starts_at": nearest_time_interval,
            }
            event = ScheduleEventMaker().create_object_and_flush(schedule_event)
            db.session.add(event)

        # Create a member that will be matched with these CAs
        for member in spec_data.get("members"):
            member["organization_name"] = org_name
            user = UserMaker().create_object_and_flush(member)
            db.session.add(user)
            result.append(user)

        db.session.flush()

        return result


class PooledCalendarMinMaker(_MakerBase):
    """
    Create Pooled Calendar Min creates 3 CA's with limited availability (a few
    available times right now, some more 8 hours later, and consistent availability
    later in the week) and a member who is eligible to match with the CA's.
    """

    def create_object(self, spec_data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        result = []

        org_name = "Pooled Calendar Min Org"

        if (
            "restrict_to_new_organization" in spec_data
            and spec_data["restrict_to_new_organization"]
        ):

            org = {
                "type": "organization",
                "name": org_name,
                "activated_at": "1 minute ago",
            }
            organization = OrganizationMaker().create_object_and_flush(org)
            db.session.add(organization)
            result.append(organization)
            spec_data["organization_id"] = organization.id
        # Create 3 CAs with limited availability over next 7 days
        datetime_now = datetime.datetime.now()
        # we want to round to the next 15-minute time slot so that the appointment times are "nice"
        nearest_time_interval = datetime.datetime.min + math.ceil(
            (datetime_now - datetime.datetime.min) / datetime.timedelta(minutes=15)
        ) * datetime.timedelta(minutes=15)
        for _ in range(3):
            ca = UserMaker().create_object_and_flush(spec_data)
            db.session.add(ca)
            result.append(ca)
            schedule_event_1 = {
                "type": "schedule_event",
                "minutes": 60,
                "practitioner": ca.email,
                "starts_at": nearest_time_interval,
            }
            schedule_event_2 = {
                "type": "schedule_event",
                "minutes": 300,
                "practitioner": ca.email,
                "starts_at": nearest_time_interval + datetime.timedelta(hours=8),
            }
            schedule_event_3 = {
                "type": "schedule_event",
                "minutes": 24 * 60 * 3,
                "practitioner": ca.email,
                "starts_at": nearest_time_interval + datetime.timedelta(days=3),
            }
            schedule_events = [schedule_event_1, schedule_event_2, schedule_event_3]
            for schedule_event in schedule_events:
                event = ScheduleEventMaker().create_object_and_flush(schedule_event)
                db.session.add(event)

        # Create a member that will be matched with these CAs
        for member in spec_data.get("members"):
            member["organization_name"] = org_name
            user = UserMaker().create_object_and_flush(member)
            db.session.add(user)
            result.append(user)

        db.session.flush()

        return result


class CareAdvocatesAvailabilityMaker(_MakerBase):
    def create_object(self, spec_data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        result = []

        if (
            "restrict_to_new_organization" in spec_data
            and spec_data["restrict_to_new_organization"]
        ):
            now = datetime.datetime.now()
            org_name = f"Test Organization {now.strftime('%Y%d%m-%H%M')}"
            org = {
                "type": "organization",
                "name": org_name,
                "activated_at": "1 minute ago",
            }
            organization = OrganizationMaker().create_object_and_flush(org)
            db.session.add(organization)
            result.append(organization)
            spec_data["organization_id"] = organization.id

        for _ in range(spec_data.get("count")):
            ca = UserMaker().create_object_and_flush(spec_data)
            datetime_now = datetime.datetime.now()
            # we want to round to the next 15-minute time slot so that the appointment times are "nice"
            nearest_time_interval = datetime.datetime.min + math.ceil(
                (datetime_now - datetime.datetime.min) / datetime.timedelta(minutes=15)
            ) * datetime.timedelta(minutes=15)
            starts_in_hour = random.randint(0, 12)
            db.session.add(ca)
            result.append(ca)
            for i in range(5):
                starts_at = nearest_time_interval + datetime.timedelta(
                    days=i, hours=starts_in_hour
                )
                schedule_event = {
                    "type": "schedule_event",
                    "starts_at": starts_at,
                    "minutes": 480,
                    "practitioner": ca.email,
                }
                event = ScheduleEventMaker().create_object_and_flush(schedule_event)
                db.session.add(event)
        db.session.flush()

        return result
