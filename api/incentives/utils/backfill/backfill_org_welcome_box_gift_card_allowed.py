import csv

from marshmallow import Schema, ValidationError, fields

from models.enterprise import Organization
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class OrganizationIncentiveAllowedSchema(Schema):
    gift_card_allowed = fields.Boolean(required=False, allow_none=True)
    welcome_box_allowed = fields.Boolean(required=True, default=False)
    organization_id = fields.Integer(required=True)


class OrganizationIncentiveAllowedBackfill:
    @classmethod
    def backfill_organization_welcome_box_gift_card_allowed(cls, file_path):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with open(file_path) as fp:
            errors = []
            for row in csv.DictReader(fp):
                org_id = row["organization_id"]
                # gift_card_allowed is nullable, so we want to handle empty cells as None
                if row["gift_card_allowed"] == "":
                    row["gift_card_allowed"] = None
                schema = OrganizationIncentiveAllowedSchema()
                try:
                    args = schema.load(row)
                except ValidationError as e:
                    errors.append(f"{e} org_id {org_id}")
                    continue
                organization = Organization.query.get(args["organization_id"])
                if not organization:
                    errors.append(
                        f"No valid organization found for org_id {args['organization_id']}"
                    )
                else:
                    try:
                        organization.gift_card_allowed = args["gift_card_allowed"]
                        organization.welcome_box_allowed = args["welcome_box_allowed"]
                        db.session.commit()
                        log.info(
                            "Organization successfully backfilled",
                            organization_id=args["organization_id"],
                            gift_card_allowed=args["gift_card_allowed"],
                            welcome_box_allowed=args["welcome_box_allowed"],
                        )
                    except Exception as e:
                        errors.append(
                            f"Exception while updating org_id {args['organization_id']}. {e}"
                        )
        return errors
