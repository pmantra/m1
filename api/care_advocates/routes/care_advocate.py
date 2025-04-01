from flask import request
from flask_restful import abort
from marshmallow import ValidationError
from maven import feature_flags

from authn.models.user import User
from care_advocates.schemas.care_advocates import (
    CareAdvocateAssignmentArgsSchema,
    CareAdvocateAssignmentResponseSchema,
    PooledAvailabilityArgsSchema,
    PooledAvailabilityResponseSchema,
    SearchArgsSchema,
    SearchResponseSchema,
)
from care_advocates.services.care_advocate import (
    CareAdvocateAlreadyAssigned,
    CareAdvocateService,
)
from care_advocates.tasks.pooled_calendar import (
    log_7_day_availability_in_pooled_calendar,
)
from common.services.api import AuthenticatedResource
from l10n.config import _negotiate_locale_wrapper
from l10n.utils import locale_to_alpha_3
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class CareAdvocateSearchException(Exception):
    ...


class CareAdvocateSearchMissingUserIdException(CareAdvocateSearchException):
    message = "Did not provide member_id"


class CareAdvocateSearchInvalidUserIdException(CareAdvocateSearchException):
    message = "Invalid Member ID"


class CareAdvocateSearchNoActiveTrackException(CareAdvocateSearchException):
    message = "User has no active tracks"


class CareAdvocatesSearchResource(AuthenticatedResource):
    def __init__(self) -> None:
        self.response_schema = SearchResponseSchema()

    def _validate_params(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not user_id:
            raise CareAdvocateSearchMissingUserIdException

        # TODO: update to call UserService()
        user = User.query.get(user_id)
        if not user:
            raise CareAdvocateSearchInvalidUserIdException

        if not user.active_tracks:
            raise CareAdvocateSearchNoActiveTrackException

    @db.from_app_replica
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        preferred_language_flag = feature_flags.bool_variation(
            "release-ca-search-preferred-language",
            default=False,
        )
        if preferred_language_flag:
            request_schema = SearchArgsSchema()
            try:
                args = request_schema.load(request.args)
            except ValidationError as e:
                log.warn(
                    "Exception validating Care Advocate Search args",
                    exception=e.messages,
                )
                abort(400, message=e.messages)

        else:
            args = request.args

        user_id = args.get("member_id")

        # TODO: Validate member_id in schema
        try:
            self._validate_params(user_id)
        except Exception as e:
            return (
                {"error": e.message},  # type: ignore[attr-defined] # "Exception" has no attribute "message"
                400,
            )

        if args.get("use_preferred_language") and preferred_language_flag:
            try:
                # NOTE: requires release-mono-api-localization to be on
                preferred_locale = _negotiate_locale_wrapper()
                member_preferred_language = locale_to_alpha_3(preferred_locale)
            except LookupError:
                abort(400, message=f"Invalid locale: {str(preferred_locale)}.")
            except Exception:
                abort(400, message="Error negotiating locale")
        else:
            member_preferred_language = None

        care_advocate_ids = (
            CareAdvocateService().get_potential_care_coordinators_for_member(
                user_id,
                member_preferred_language,
                availability_before=args.get("availability_before"),
            )
        )
        num_care_advocates = len(care_advocate_ids)

        log.info(
            "Found potential care coordinators for member",
            care_advocate_ids=care_advocate_ids,
            user_id=user_id,
            num_care_advocates=num_care_advocates,
        )
        care_advocate_ids = CareAdvocateService().keep_existing_ca_if_valid_and_member_transitioning_tracks(
            user_id, care_advocate_ids
        )

        (
            care_advocate_ids,
            soonest_next_availability,
        ) = CareAdvocateService().limit_care_advocate_ids_by_next_availability(
            user_id, care_advocate_ids
        )

        log_7_day_availability_in_pooled_calendar.delay(
            care_advocate_ids=care_advocate_ids,
            user_id=int(user_id),
            team_ns="care_discovery",
        )

        return self.response_schema.dump(
            {
                "care_advocate_ids": care_advocate_ids,
                "soonest_next_availability": soonest_next_availability,
            }
        )


class CareAdvocatesPooledAvailabilityResource(AuthenticatedResource):
    @db.from_app_replica
    def get(self) -> PooledAvailabilityResponseSchema:
        request_schema = PooledAvailabilityArgsSchema()
        try:
            args = request_schema.load(request.args)
        except ValidationError as e:
            log.warn(
                "Exception validating PooledAvailability args", exception=e.messages
            )
            abort(400, message=e.messages)

        log.info(
            "Starting get request for CareAdvocatesPooledAvailabilityResource",
            ca_ids=args["ca_ids"],
            start_at=args["start_at"],
            end_at=args["end_at"],
        )

        try:
            pooled_availability = CareAdvocateService().build_pooled_availability(
                ca_ids=args["ca_ids"],
                start_at=args["start_at"],
                end_at=args["end_at"],
                user=self.user,
            )

            log.info(
                "Successfully built pooled availability",
                ca_ids=args["ca_ids"],
                start_at=str(args["start_at"]),
                end_at=str(args["end_at"]),
                n_timeslot=len(pooled_availability),
            )

            response_schema = PooledAvailabilityResponseSchema()
            return response_schema.dump(pooled_availability)

        # todo: remove generic exception handler
        except Exception as e:
            log.warning("Exception building pooled availability", exception=e.message)  # type: ignore[attr-defined] # "Exception" has no attribute "message"
            return (  # type: ignore[return-value] # Incompatible return value type (got "Tuple[Dict[str, str], int]", expected "PooledAvailabilityResponseSchema")
                {"error": f"Exception building pooled availability. {str(e)}"},
                500,
            )


class CareAdvocatesAssignResource(AuthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        request_schema = CareAdvocateAssignmentArgsSchema()
        try:
            args = request_schema.load(request.json if request.is_json else None)  # type: ignore[arg-type] # Argument 1 to "load" of "Schema" has incompatible type "Optional[Any]"; expected "Union[Mapping[str, Any], Iterable[Mapping[str, Any]]]"
        except ValidationError as e:
            log.warn(
                "Exception validating CareAdvocateAssignment args", exception=str(e)
            )
            abort(400, message=e.messages)

        log.info(
            "Starting get request for CareAdvocatesAssignResource",
            user_id=args["member_id"],
            ca_ids=args["ca_ids"],
        )

        try:
            assigned_ca_id = CareAdvocateService().assign_care_advocate(
                ca_ids=args["ca_ids"], user_id=args["member_id"]
            )

            log.info(
                "Successfully assigned care advocate",
                user_id=args["member_id"],
                care_advocate_id=assigned_ca_id,
            )

            response_schema = CareAdvocateAssignmentResponseSchema()
            return response_schema.dump(assigned_ca_id)

        except CareAdvocateAlreadyAssigned as e:
            response_schema = CareAdvocateAssignmentResponseSchema()
            return response_schema.dump(e.selected_cx)

        except Exception as e:
            log.warning("Exception assigning care advocate", exception=str(e))
            return (
                {"error": f"Exception assigning care advocate. {str(e)}"},
                500,
            )
