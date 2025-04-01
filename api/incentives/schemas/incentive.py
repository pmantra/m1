from marshmallow import Schema, ValidationError, fields

from incentives.models.incentive import IncentiveAction
from models.tracks import TrackName


class IncentiveSchemaMsg(str):
    INVALID_INCENTIVIZED_ACTION = "Invalid incentivized action"


def validate_incentivized_action(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if value in [ia._name_.lower() for ia in [*IncentiveAction]]:
        return value
    raise ValidationError(IncentiveSchemaMsg.INVALID_INCENTIVIZED_ACTION)


def validate_track(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not value or not TrackName.isvalid(value):
        raise ValidationError(f"'{value}' is not a valid track")
    return value


class UserIncentiveArgsSchema(Schema):
    incentivized_action = fields.String(
        required=True, validate=validate_incentivized_action
    )
    track = fields.String(required=True, validate=validate_track)


class UserIncentiveResponseSchema(Schema):
    incentive_id = fields.Integer()
    incentive_type = fields.String()
    design_asset = fields.String()
    amount = fields.Integer()
