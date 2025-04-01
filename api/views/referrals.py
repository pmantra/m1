import enum

from flask import request
from flask_babel import lazy_gettext
from flask_restful import abort
from marshmallow_v1 import Schema, fields
from sqlalchemy.orm.exc import NoResultFound

from appointments.models.payments import Credit
from authn.models.user import User
from common.services import ratelimiting
from common.services.api import AuthenticatedResource, UnauthenticatedResource
from models.referrals import ReferralCode
from storage.connection import db
from utils import security
from utils.log import logger
from views.credits import CreditMetaSchema
from views.schemas.common import MavenDateTime, PaginableOutputSchema

log = logger(__name__)


class ReferralCodeValueSchema(Schema):
    value = fields.Integer()
    description = fields.String()
    type = fields.String(attribute="for_user_type")


class ReferralCodeUseSchema(Schema):
    used_at = MavenDateTime(attribute="created_at")
    used_by = fields.Integer(attribute="user_id")
    values = fields.Nested(ReferralCodeValueSchema, many=True, attribute="code.values")
    meta = fields.Method("get_meta")

    @classmethod
    def get_meta(cls, code_use, _context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = User.query.get(code_use.user_id)
        cc = Credit.available_for_user(user).all()
        total_credit = sum(c.amount for c in cc)
        schema = CreditMetaSchema()
        return schema.dump({"total_credit": total_credit}).data


class ReferralCodeSchema(Schema):
    code = fields.String()
    description = fields.String()
    created_at = MavenDateTime()
    expires_at = MavenDateTime()
    values = fields.Nested(ReferralCodeValueSchema, many=True)
    uses = fields.Nested(ReferralCodeUseSchema, many=True)
    available_uses = fields.Integer()


class ReferralCodesSchema(PaginableOutputSchema):
    data = fields.Nested(ReferralCodeSchema, many=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")


class ReferralCodeInfoSchema(Schema):
    value = fields.Integer()
    code = fields.String()


class ReferralErrorMessages(enum.Enum):
    unknown = lazy_gettext("views_referrals_unknown")
    missing_data = lazy_gettext("views_referrals_missing_data")
    does_not_exist = lazy_gettext("views_referrals_does_not_exist")
    already_used_code = lazy_gettext("views_referrals_already_applied")
    expired = lazy_gettext("views_referrals_expired")
    has_booked = lazy_gettext("views_referrals_too_late")
    owner = lazy_gettext("views_referrals_not_you")
    no_code = lazy_gettext("views_referrals_no_code")
    code_not_found = lazy_gettext("views_referrals_not_found")
    invalid = lazy_gettext("views_referrals_invalid")


REFERRAL_ERROR = lazy_gettext("views_referrals_main_message")


class ReferralCodeInfoResource(UnauthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        code = request.args.get("referral_code")
        if not code:
            abort(400, message=str(ReferralErrorMessages.no_code.value))

        try:
            code = (
                db.session.query(ReferralCode).filter(ReferralCode.code == code).one()
            )
        except NoResultFound:
            abort(400, message=str(ReferralErrorMessages.code_not_found.value))
        else:
            user = self._get_user(request.args.get("encoded_user_id"))

            if user:
                valid, reason = code.is_valid_for_user(user)
            else:
                log.debug("No user for code info for %s", code)
                valid = code.is_valid

            if not valid:
                log.debug("%s is not valid!", code)
                abort(400, message=str(ReferralErrorMessages.invalid.value))

            value = 0
            for _val in code.values:
                if _val.for_user_type == "member":
                    value = _val.value
                    break

            out_schema = ReferralCodeInfoSchema()
            json_response = {"value": value, "code": code.code}
            marshmallow_response = out_schema.dump(json_response).data
            if json_response != marshmallow_response:
                log.info(
                    "FM - /v1/referral_code_info discrepancy",
                    json_response=str(json_response),
                    marshmallow_response=str(marshmallow_response),
                )
            else:
                log.info("FM - /v1/referral_code_info equal response")

            return marshmallow_response

    def _get_user(self, encoded_user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.user:
            return self.user
        elif encoded_user_id:
            decoded_id = security.check_user_id_encoded_token(encoded_user_id)
            if decoded_id:
                log.info("Bad encoded_user_id!")
                abort(400, message="Bad ID!")
            return User.query.get_or_404(decoded_id)


class ReferralCodesGetArgs(Schema):
    owner = fields.Integer(required=True)

    class Meta:
        strict = True


class ReferralCodesResource(AuthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema = ReferralCodesGetArgs()
        args = schema.load(request.args).data

        if args["owner"] != self.user.id:
            abort(403, message=str(ReferralErrorMessages.owner.value))

        referrals = (
            db.session.query(ReferralCode)
            .filter(ReferralCode.user_id == self.user.id)
            .order_by(ReferralCode.created_at.asc())
        )

        schema = ReferralCodesSchema()
        return schema.dump({"data": referrals.all()}).data


class ReferralCodeUseResource(AuthenticatedResource):
    @ratelimiting.ratelimited(attempts=3, cooldown=120)
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        args = post_request(request.json if request.is_json else None)
        if "referral_code" not in args:
            abort(400, message=str(ReferralErrorMessages.missing_data.value))

        code = args.get("referral_code")
        log.debug("Using referral code %s", code)

        use = None
        reason = str(ReferralErrorMessages.unknown.value)
        try:
            r_code = (
                db.session.query(ReferralCode).filter(ReferralCode.code == code).one()
            )
            use, reason = r_code.use_with_reason(self.user)
        except NoResultFound:
            # This is what you should get on the first time
            log.info(f"Unable to find referral code matching: {code}")
            abort(422, message=str(ReferralErrorMessages.does_not_exist.value))

        if use:
            schema = ReferralCodeUseSchema()
            return schema.dump(use).data, 201
        else:
            reasons_copy = {
                "already_used_code": str(ReferralErrorMessages.already_used_code.value),
                "expired": str(ReferralErrorMessages.expired.value),
                "has_booked": str(ReferralErrorMessages.has_booked.value),
            }

            message_default = REFERRAL_ERROR.format(reason=reason)
            # implicit DB rollback applies in this case...
            log.info(
                "Failed to apply a referral code due to invalid state.",
                reason=reason,
                code=code,
            )
            abort(422, message=reasons_copy.get(reason, message_default))


def post_request(request_json: dict) -> dict:
    if not request_json:
        return {}
    return {"referral_code": str(request_json["referral_code"])}
