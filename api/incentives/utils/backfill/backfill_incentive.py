import csv

from marshmallow import Schema, ValidationError, fields

from incentives.models.incentive import Incentive, IncentiveDesignAsset, IncentiveType
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def validate_incentive_type(incentive_type):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if incentive_type in [it.value for it in [*IncentiveType]]:
        return incentive_type
    raise ValidationError("Invalid incentive_type")


def validate_design_asset(design_asset):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if design_asset in [da.value for da in [*IncentiveDesignAsset]]:
        return design_asset
    raise ValidationError("Invalid design_asset")


class IncentiveSchema(Schema):
    type = fields.String(required=True, validate=validate_incentive_type)
    name = fields.String(required=True)
    amount = fields.Integer(required=False, allow_none=True)
    vendor = fields.String(required=True)
    design_asset = fields.String(required=True, validate=validate_design_asset)
    active = fields.Boolean(required=True)


class IncentiveBackfill:
    @classmethod
    def backfill_incentive(cls, file_path):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with open(file_path) as fp:
            errors = []
            for row in csv.DictReader(fp):
                name = row.get("name")
                # amount is nullable, so we want to handle empty cells as None
                if row["amount"] == "":
                    row["amount"] = None
                schema = IncentiveSchema()
                try:
                    args = schema.load(row)
                except ValidationError as e:
                    errors.append(f"{e} - NAME: {name}")
                    continue
                try:
                    new_incentive = Incentive(
                        type=IncentiveType(args["type"]),
                        name=args["name"],
                        amount=args["amount"],
                        vendor=args["vendor"],
                        design_asset=IncentiveDesignAsset(args["design_asset"]),
                        active=args["active"],
                    )
                    db.session.add(new_incentive)
                    db.session.commit()
                    log.info(
                        "Incentive successfully backfilled",
                        incentive_id=new_incentive.id,
                        name=args["name"],
                    )
                except Exception as e:
                    errors.append(
                        f"Exception while creating Incentive {args['name']}. {e.message}"  # type: ignore[attr-defined] # "Exception" has no attribute "message"
                    )
        return errors
