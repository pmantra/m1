import csv

from marshmallow import Schema, ValidationError, fields

from geography import repository as geography_repository
from geography.utils import validate_country_code
from incentives.models.incentive import (
    Incentive,
    IncentiveAction,
    IncentiveOrganization,
    IncentiveOrganizationCountry,
)
from incentives.services.incentive_organization import IncentiveOrganizationService
from models.enterprise import Organization
from models.tracks.track import TrackName
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def validate_incentivized_action(incentivized_action):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if incentivized_action in [it.name for it in [*IncentiveAction]]:
        return incentivized_action
    raise ValidationError("Invalid incentivized_action")


class IncentiveOrganizationSchema(Schema):
    organization_id = fields.Integer(required=True)
    organization_name = fields.String(required=True)
    action = fields.String(required=True, validate=validate_incentivized_action)
    incentive_name = fields.String(required=True)
    track_name = fields.String(required=True)
    countries = fields.String(required=True)


class IncentiveOrganizationBackfill:
    @classmethod
    def backfill_incentive_organization(cls, file_path):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with open(file_path) as fp:
            errors = []
            all_countries = geography_repository.CountryRepository().all()
            for row in csv.DictReader(fp):
                org_id = row.get("organization_id")
                organization = Organization.query.get(org_id)
                if not organization:
                    errors.append(f"Organization {org_id} does not exist")
                    continue
                schema = IncentiveOrganizationSchema()
                try:
                    args = schema.load(row)
                except ValidationError as e:
                    errors.append(f"{e} - Organization: {org_id}")
                    continue
                incentive = (
                    db.session.query(Incentive)
                    .filter(Incentive.name == args["incentive_name"])
                    .first()
                )
                if not incentive:
                    errors.append(f"Incentive {args['incentive_name']} does not exist")
                    continue
                try:
                    IncentiveOrganizationService().check_eligibility(
                        organization=organization,
                        incentive=incentive,
                    )
                    track_name = cls._validate_track_name(args["track_name"].lower())
                    IncentiveOrganizationService().check_for_duplicates(
                        organization=organization,
                        action=args["action"],
                        track_name=track_name,
                        active=True,
                        incentive_organization_id=None,
                    )
                    incentive_id = (
                        db.session.query(Incentive.id)
                        .filter(Incentive.name == args["incentive_name"])
                        .first()
                    )
                    new_incentive_org = IncentiveOrganization(
                        organization_id=args["organization_id"],
                        incentive_id=incentive_id[0] if incentive_id else None,
                        action=args["action"],
                        track_name=track_name,
                        active=True,
                    )
                    db.session.add(new_incentive_org)
                    # need to commit so incentive-org exists before creating incentive-org-country
                    db.session.commit()
                    if args["countries"] == "All":
                        for country in all_countries:
                            new_incentive_org_country = IncentiveOrganizationCountry(
                                incentive_organization_id=new_incentive_org.id,
                                country_code=country.alpha_2,
                            )
                            db.session.add(new_incentive_org_country)
                    else:
                        for country_code in args["countries"].split(","):
                            country_code = cls._validate_country_code(
                                country_code.strip()
                            )
                            new_incentive_org_country = IncentiveOrganizationCountry(
                                incentive_organization_id=new_incentive_org.id,
                                country_code=country_code,
                            )
                            db.session.add(new_incentive_org_country)
                    db.session.commit()
                    log.info(
                        "IncentiveOrg successfully backfilled",
                        incentive_org_id=new_incentive_org.id,
                        incentive_name=args["incentive_name"],
                        organization_id=args["organization_id"],
                    )
                except Exception as e:
                    # value errors do not have 'message' property, but our custom errors do
                    errors.append(
                        f"Exception creating IncentiveOrg incentive_name: {args['incentive_name']}, org_id: {args['organization_id']}. {e.message if hasattr(e, 'message') else e}"
                    )
        return errors

    @classmethod
    def _validate_track_name(cls, track_name: str) -> str:
        if track_name == "None":
            raise ValueError("Track can not be None")
        if track_name and not TrackName.isvalid(track_name):
            raise ValueError(f"'{track_name}' is not a valid track name")
        return track_name

    @classmethod
    def _validate_country_code(cls, country_code):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return validate_country_code(country_code)
