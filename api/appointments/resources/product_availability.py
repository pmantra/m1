from datetime import datetime, timedelta

from flask import request
from flask_restful import abort
from marshmallow import Schema, ValidationError, fields
from sqlalchemy.orm import joinedload

from appointments.models.payments import Credit
from appointments.utils.booking import AvailabilityCalculator, AvailabilityTools
from common import stats
from common.services.api import AuthenticatedResource
from models.products import Product
from models.profiles import PractitionerProfile
from storage.connection import db
from utils.exceptions import log_exception_message
from utils.log import logger
from views.schemas.common_v3 import MavenDateTime

log = logger(__name__)


class ProductAvailabilitySchema(Schema):
    scheduled_start = MavenDateTime()
    scheduled_end = MavenDateTime()
    total_available_credits = fields.Integer()


class ProductAvailabilityMetaSchema(Schema):
    starts_at = MavenDateTime()
    ends_at = MavenDateTime()
    practitioner_id = fields.Integer()


class ProductsAvailabilitySchema(Schema):
    data = fields.Nested(ProductAvailabilitySchema, many=True)
    meta = fields.Nested(ProductAvailabilityMetaSchema)
    duration = fields.Integer()
    practitioner_id = fields.Integer()
    product_id = fields.Integer()
    product_price = fields.Float()
    total_available_credits = fields.Integer()


class ProductAvailabilityArgs(Schema):
    starts_at = MavenDateTime(required=False)
    ends_at = MavenDateTime(required=False)


class ProductAvailabilityResource(AuthenticatedResource):
    def get(self, product_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        schema = ProductAvailabilityArgs()
        try:
            args = schema.load(request.args)
        except ValidationError as exc:
            log.warn(exc.messages)
            abort(400, message=exc.messages)

        starts_at = args.get("starts_at") or datetime.utcnow()
        ends_at = args.get("ends_at") or starts_at + timedelta(days=7)

        log.info(
            "Starting GET request for ProductAvailabilityResource",
            start_at=starts_at,
            ends_at=ends_at,
            product_id=product_id,
        )

        now = datetime.utcnow()
        one_day_ago = now - timedelta(days=1)
        four_weeks_from_now = now + timedelta(days=7 * 4)

        # Clamp our boundaries to acceptable range
        starts_at = max(starts_at, one_day_ago)
        ends_at = min(ends_at, four_weeks_from_now)

        error_msg = None
        if ends_at < one_day_ago:
            error_msg = (
                "[ends_at] Availability cannot be queried more than 1 day in the past."
            )
        elif starts_at > four_weeks_from_now:
            error_msg = "[starts_at] Availability cannot be queried more than 4 weeks in the future."
        elif starts_at > ends_at:
            error_msg = "Availability query must have starts_at <= ends_at."

        if error_msg:
            log_exception_message(error_msg)
            return {"message": error_msg}, 400

        product = Product.query.options(
            joinedload("practitioner").joinedload("schedule")
        ).get_or_404(product_id)
        profile = (
            db.session.query(PractitionerProfile)
            .filter(PractitionerProfile.user_id == product.practitioner.id)
            .options(joinedload("user").joinedload("schedule"))
            .one_or_none()
        )
        if not profile:
            log.warn("Product exists without connected practitioner profile.")
            abort(400, "Profile not found for practitioner's product.")

        starts_at = AvailabilityTools.pad_and_round_availability_start_time(
            starts_at,
            profile.booking_buffer,
            profile.rounding_minutes,
        )

        log.info(
            "GET ProductAvailabilityResource: Starting to compute availability",
            start_at=starts_at,
            ends_at=ends_at,
            product_id=product_id,
            practitioner_id=product.practitioner.id,
            member_id=self.user.id,
        )
        availability = AvailabilityCalculator(
            practitioner_profile=profile, product=product
        ).get_availability(starts_at, ends_at, member=self.user)

        meta = {
            "starts_at": starts_at,
            "ends_at": ends_at,
            "practitioner_id": product.user_id,
        }

        if not availability and profile.is_cx:
            stats.increment(
                metric_name="api.views.products.product_availability.get.no_availability",
                pod_name=stats.PodNames.MPRACTICE_CORE,
                tags=[f"practitioner_id:{profile.user_id}", "error:true"],
            )
            log.warn(
                "no availability found for care advocate",
                care_advocate_id=profile.user_id,
                user_id=self.user.id,
                starts_at=starts_at,
                ends_at=ends_at,
            )

        log.info(
            f"Total availabilities shown {len(availability)} ",
            practitioner_id=product.practitioner.id,
            starts_at=starts_at,
            ends_at=ends_at,
        )

        available_credits = Credit.available_for_member_time(self.user.id, starts_at)
        total_available_credits = sum(c.amount for c in available_credits)

        schema = ProductsAvailabilitySchema()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "ProductsAvailabilitySchema", variable has type "ProductAvailabilityArgs")
        return schema.dump(
            {
                "data": availability,
                "meta": meta,
                "practitioner_id": product.practitioner.id,
                "duration": product.minutes,
                "product_id": product.id,
                "product_price": product.price,
                "total_available_credits": total_available_credits,
            }
        )
