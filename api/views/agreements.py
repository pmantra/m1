from __future__ import annotations

import ddtrace
from flask import request
from httpproblem import Problem, problem
from marshmallow import Schema, fields, post_load, validates
from marshmallow.exceptions import ValidationError
from sqlalchemy.orm.exc import NoResultFound

import eligibility
from common.services.api import AuthenticatedResource, UnauthenticatedResource
from models.profiles import Agreement, AgreementAcceptance, AgreementNames, Language
from storage.connection import db
from utils.log import logger
from views.schemas.common import from_validation_error

log = logger(__name__)


class AgreementsPostSchema(Schema):
    name = fields.String(required=True)
    version = fields.Integer(required=True)
    accepted = fields.Bool(required=False, default=True, load_default=True)
    display_name = fields.String()
    optional = fields.Bool()

    @validates("name")
    def validate_name(self, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            AgreementNames(name)
        except ValueError:
            raise ValidationError("Agreement name not found.", field_name="name")

    @post_load
    def parse_name(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        data["name"] = AgreementNames(data["name"])
        return data


class AgreementsResource(AuthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Creates a user agreement"""
        schema = AgreementsPostSchema(many=True)

        try:
            request_json = request.json if request.is_json else None
            agreements_args = schema.load(request_json["agreements"])
        except ValidationError as e:
            log.warning(
                f"{AgreementsPostSchema.__name__} failed validation.",
                user_id=self.user.id,
                exception=e,
            )
            return from_validation_error(e, many=True)

        if len(agreements_args) == 0:
            message = "Agreements field cannot be empty."
            errors = problem(
                status=400,
                detail=message,
            )
            return {"data": None, "errors": [errors]}, 400

        not_found_errors = []
        bad_request_errors = []
        created = []
        updated = []

        for agreement_arg in agreements_args:
            name = agreement_arg["name"]
            version = agreement_arg["version"]
            accepted = agreement_arg["accepted"]

            agreement = (
                db.session.query(Agreement)
                .filter(
                    Agreement.name == name,
                    Agreement.version == version,
                )
                .first()
            )

            if agreement is None:
                message = f"Could not find version {version} of {name.value}"
                not_found_errors.append(
                    problem(
                        status=404,
                        detail=message,
                    )
                )
                log.warn(message)
                continue

            if not agreement.optional and not accepted:
                message = (
                    f"{agreement.display_name} is not optional and must be agreed to"
                )
                bad_request_errors.append(
                    problem(
                        status=400,
                        detail=message,
                    )
                )
                log.warn(message)
                continue

            existing_user_agreement = (
                db.session.query(AgreementAcceptance)
                .filter(
                    AgreementAcceptance.user_id == self.user.id,
                    AgreementAcceptance.agreement_id == agreement.id,
                )
                .first()
            )

            if existing_user_agreement is None:
                new_user_agreement = AgreementAcceptance(
                    user=self.user,
                    agreement=agreement,
                    accepted=accepted,
                )
                created.append(new_user_agreement)
                db.session.add(new_user_agreement)
            elif existing_user_agreement.accepted != accepted:
                existing_user_agreement.accepted = accepted
                updated.append(existing_user_agreement)
                db.session.add(existing_user_agreement)

        if not_found_errors:
            db.session.rollback()
            return {"data": None, "errors": not_found_errors}, 404
        if bad_request_errors:
            db.session.rollback()
            return {"data": None, "errors": bad_request_errors}, 400

        db.session.commit()

        for agreement in created:
            agreement.audit_creation()
        for agreement in updated:
            agreement.audit_update()

        return {"data": {"message": "Success"}, "errors": []}, 200


class AgreementResource(UnauthenticatedResource):
    def get(self, agreement_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation

        try:
            agreement_name = AgreementNames(agreement_name)

        except ValueError:
            return (
                {
                    "data": None,
                    "errors": [
                        {
                            "code": "BAD_REQUEST",
                            "message": "Agreement name does not match enum",
                        }
                    ],
                },
                400,
            )

        language = request.args.get("lang")
        lang = None
        if language:
            lang = Language.query.filter_by(iso_639_3=language).one_or_none()
            if not lang:
                raise Problem(
                    400,
                    detail="The given language is not supported",
                )

        if version := request.args.get("version"):
            return self._get_by_version(agreement_name, version, lang)
        else:
            return self._get_latest(agreement_name, lang)

    def _get_latest(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, agreement_name: AgreementNames, language: Language | None = None
    ):
        agreement = Agreement.latest_version(agreement_name, language=language)

        if agreement:
            return self._okay(agreement)

        log.warning(
            "Client attempted to fetch non-existent agreement",
            agreement_name=agreement_name.value,
        )
        return (
            {
                "data": None,
                "errors": [
                    {
                        "code": "BAD_REQUEST",
                        "message": "No version of this agreement has been established.",
                    }
                ],
            },
            404,
        )

    def _get_by_version(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        agreement_name: AgreementNames,
        version: str,
        language: Language | None = None,
    ):
        try:
            version_num = int(version)
        except ValueError:
            return (
                {
                    "data": None,
                    "errors": [
                        {
                            "code": "BAD_REQUEST",
                            "message": "Please provide a valid integer for version number",
                        }
                    ],
                },
                400,
            )

        try:
            agreement = Agreement.get_by_version(agreement_name, version_num, language)
            return self._okay(agreement)

        except NoResultFound:
            log.warning(
                "Client attempted to fetch non-existent version on agreement",
                agreement_name=agreement_name.value,
                version=version,
            )
            return (
                {
                    "data": None,
                    "errors": [
                        {
                            "code": "BAD_REQUEST",
                            "message": "Please provide a valid version number for this agreement",
                        }
                    ],
                },
                404,
            )

    @staticmethod
    def _okay(agreement: Agreement):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            {
                "data": {
                    "name": agreement.name.value,  # type: ignore[union-attr] # Item "str" of "Optional[str]" has no attribute "value" #type: ignore[union-attr] # Item "None" of "Optional[str]" has no attribute "value"
                    "display_name": agreement.display_name,
                    "agreement": agreement.html,
                    "version": agreement.version,
                    "optional": agreement.optional,
                    "language": agreement.language.iso_639_3
                    if agreement.language
                    else None,
                },
                "errors": [],
            },
            200,
        )


class PendingAgreementsResource(AuthenticatedResource):
    @ddtrace.tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return {
            "organization": self._get_pending_organization_agreements(),
            "user": self._get_pending_user_agreements(),
        }

    def _get_pending_organization_agreements(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Get a list of info about the pending agreements for the User that are specific to that User's organization.
        An agreement is pending if we do not have a corresponding AgreementAcceptance.
        @return: list of dictionaries containing the name, display_name, and version of the agreement
        """
        verification_svc: eligibility.EnterpriseVerificationService = (
            eligibility.get_verification_service()
        )
        organization_ids = verification_svc.get_eligible_organization_ids_for_user(
            user_id=self.user.id
        )
        return self._map_pending_agreements(
            self.user.get_pending_organization_agreements(
                organization_ids=organization_ids
            )
        )

    def _get_pending_user_agreements(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Get a list of info about the pending agreements for the User that are not specific to that User's organization.
        An agreement is pending if we do not have a corresponding AgreementAcceptance.
        @return: list of dictionaries containing the name, display_name, and version of the agreement
        """
        return self._map_pending_agreements(self.user.pending_user_agreements)

    @staticmethod
    def _map_pending_agreements(pending_agreements: list[Agreement]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return [
            {
                "name": pending_agreement.name.value,  # type: ignore[union-attr] # Item "str" of "Optional[str]" has no attribute "value" #type: ignore[union-attr] # Item "None" of "Optional[str]" has no attribute "value"
                "display_name": pending_agreement.display_name,
                "version": pending_agreement.version,
                "optional": pending_agreement.optional,
            }
            for pending_agreement in pending_agreements
        ]
