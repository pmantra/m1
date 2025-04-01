from __future__ import annotations

import uuid
from datetime import date, datetime
from traceback import format_exc
from typing import Any, Optional

import ddtrace
import pytz
from flask import make_response, request
from flask_restful import abort
from httpproblem import Problem
from ldclient import Stage
from marshmallow import ValidationError
from maven.feature_flags import migration_variation
from sqlalchemy.orm.exc import NoResultFound

from authn.models.user import User
from authz.models.roles import ROLES
from common.health_profile.health_profile_service_client import (
    HealthProfileServiceClient,
)
from common.health_profile.health_profile_service_models import (
    ClinicalStatus,
    ConditionType,
    MemberCondition,
    Modifier,
    PregnancyAndRelatedConditions,
)
from common.services.api import PermissionedCareTeamResource
from health.models.health_profile import HealthProfile
from health.models.health_profile_schema import ChildSchema, HealthProfileSchema
from health.models.risk_enums import ModifiedReason
from health.schema.pregnancy import (
    PatchPregnancyAndRelatedConditionsRequestSchema,
    PregnancyAndRelatedConditionsSchema,
    PutPregnancyAndRelatedConditionsRequestSchema,
)
from health.services.health_profile_service import HealthProfileService
from health.services.member_risk_service import MemberRiskService
from health.tasks import update_health_profile_in_braze
from health.utils.constants import MIGRATE_PREGNANCY_DATA_FROM_MONO_TO_HPS
from models import tracks
from models.tracks import ChangeReason
from storage.connection import db
from utils.braze_events import biological_sex
from utils.exceptions import ProgramLifecycleError
from utils.launchdarkly import user_context
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)


class HealthProfileResource(PermissionedCareTeamResource):
    def _log_exception(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        message: str,
        context: Optional[dict] = None,
    ):
        if context is None:
            context = {}
        context["exception"] = format_exc()
        self._log_error(message, context)

    def _log_error(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        message: str,
        context: Optional[dict] = None,
    ):
        if context is None:
            context = {}
        if self.user is not None:
            context["user"] = self.user.id
        log.error(f"HealthProfileResource: {message}", context=context)

    def _log_info(
        self,
        message: str,
        context: Optional[dict] = None,
    ) -> None:
        if context is None:
            context = {}
        if self.user is not None:
            context["user"] = self.user.id
        log.info(f"HealthProfileResource: {message}", context=context)

    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        target_user = self.target_user(user_id)
        json = {}
        try:
            hp_service = HealthProfileService(target_user)
            health_profile = target_user.health_profile
            if health_profile is None:
                return {}

            json = health_profile.json
            if not json:
                return {}
            json[
                "fertility_treatment_status"
            ] = hp_service.get_fertility_treatment_status()
            return json
        except Exception as e:
            self._log_exception(
                "Error Getting Health Profile",
                {"target_user": target_user.id, "health_profile_json": str(json)},
            )
            raise e

    @ddtrace.tracer.wrap()
    def put(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self.target_user(user_id)
        profile = user.health_profile
        if profile is None:
            raise Problem(404, detail="User does not have Health Profile")
        due_date = profile.due_date
        last_child_birthday = profile.last_child_birthday
        sex_at_birth = profile.json.get("sex_at_birth")
        schema = HealthProfileSchema()
        request_json = request.json if request.is_json else None
        mr_service = MemberRiskService(
            user.id,
            commit=True,
            modified_by=user.id,
            modified_reason=ModifiedReason.PREGNANCY_ONBOARDING,
        )
        try:
            data = schema.load(request_json)
        except ValidationError as e:
            self._log_exception(
                "ValidationError",
                {
                    "details": e.normalized_messages(),
                    "request_json": str(request_json),
                },
            )
            # replicating behavior of legacy @MavenSchema.error_handler
            abort(400, status_code=400, error=e.normalized_messages())
        try:
            if "children" in data:
                # generate children ids
                data["children"] = self._edit_children(None, data["children"])

            # re-serialize validated data - record profile json as a string, not a dictionary
            profile.json = schema.dump(data)
            if "birthday" in data:
                self._set_birthdate(profile, data["birthday"])
            if "fertility_treatment_status" in data:
                self._set_fertility_treatment_status(
                    user, data["fertility_treatment_status"]
                )

            db.session.add(profile)

            tracks.on_health_profile_update(
                user=user,
                change_reason=ChangeReason.API_PUT_HEALTH_PROFILE_UPDATE,
            )

            db.session.commit()

            if data.get("due_date") and data["due_date"] != due_date:
                health_profile_service = HealthProfileService(
                    user=user, accessing_user=self.user
                )
                modifier = Modifier(
                    id=user.id,
                    name=user.full_name,
                    role=ROLES.member,
                )
                health_profile_service.update_due_date_in_hps(
                    data["due_date"], modifier
                )

            try:
                if "sex_at_birth" in data and data["sex_at_birth"] != sex_at_birth:
                    biological_sex(user, biological_sex=data["sex_at_birth"])

                self._update_mailchimp_subscriber(
                    profile, due_date, last_child_birthday
                )

                # Assume the first time to input due_date is onboarding pregnancy
                if "due_date" in data and due_date is None:
                    mr_service.create_trimester_risk_flags(data.get("due_date"))
            except Exception:
                # Don't let this error affect the return value
                self._log_exception(
                    "Error Sending to Braze or MailChimp",
                    {"request_body": str(request_json)},
                )
            return profile.json
        except Exception as e:
            db.session.rollback()
            self._log_error(
                "Error setting Health Profile",
                {
                    "request_json": str(request_json),
                    "profile_json": str(profile.json),
                },
            )
            raise e

    def patch(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Partial modification of Health Profile
        :param user_id: the user whose health profile to be modified.
        :return:
        """
        user = self.target_user(user_id)

        try:
            profile = (
                db.session.query(HealthProfile)
                .filter(HealthProfile.user_id == user.id)
                .one()
            )
            due_date = profile.due_date
            last_child_birthday = profile.last_child_birthday
            sex_at_birth = profile.json.get("sex_at_birth")
        except NoResultFound:
            abort(404)
        else:
            data = request.json if request.is_json else {}
            schema = HealthProfileSchema()
            try:
                data = schema.load(request.json if request.is_json else {})
            except ValidationError as error:
                # replicating behavior of legacy @MavenSchema.error_handler
                abort(400, status_code=400, error=error.normalized_messages())

            # re-serialize validated data
            profile_data = schema.dump(data)
            for k in profile_data:
                if "children" == k:
                    profile.json[k] = self._edit_children(
                        profile.json.get(k), profile_data[k]
                    )
                else:
                    profile.json[k] = profile_data[k]
            if "birthday" in profile_data:
                try:
                    birthday_data = profile_data["birthday"]
                    if isinstance(birthday_data, date):
                        profile.date_of_birth = birthday_data
                    elif isinstance(birthday_data, str):
                        profile.date_of_birth = datetime.strptime(
                            birthday_data, "%Y-%m-%d"
                        ).date()
                except Exception:
                    log.info(
                        "Cannot retrieve birthday in HealthProfileResource patch",
                        error=format_exc(),
                    )
            db.session.add(profile)
            try:
                tracks.on_health_profile_update(
                    user=user,
                    change_reason=ChangeReason.API_PATCH_HEALTH_PROFILE_UPDATE,
                )
                db.session.commit()

                if data.get("due_date") and data["due_date"] != due_date:
                    health_profile_service = HealthProfileService(
                        user=user, accessing_user=self.user
                    )
                    modifier = Modifier(
                        id=user.id,
                        name=user.full_name,
                        role=ROLES.member,
                    )
                    health_profile_service.update_due_date_in_hps(
                        data["due_date"], modifier
                    )
            except tracks.TrackLifecycleError as e:
                log.error(e)
                db.session.rollback()
                abort(400, message=str(e))
            # TODO: [Track] Phase 3 - drop this.
            except ProgramLifecycleError as e:
                log.log(e.log_level, e)
                db.session.rollback()
                abort(e.status_code, message=e.display_message)

            if profile_data["sex_at_birth"] != sex_at_birth:
                biological_sex(user, biological_sex=profile_data["sex_at_birth"])

            self._update_mailchimp_subscriber(profile, due_date, last_child_birthday)

            return profile.json

    def _set_birthdate(self, profile: HealthProfile, birthday_data: Any):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            if isinstance(birthday_data, date):
                profile.date_of_birth = birthday_data
            elif isinstance(birthday_data, str):
                profile.date_of_birth = datetime.strptime(
                    birthday_data, "%Y-%m-%d"
                ).date()
        except Exception:
            # log & ignore
            self._log_exception(
                "Cannot parse birthday into date...Ignoring",
                {"date": str(birthday_data)},
            )

    def _set_fertility_treatment_status(self, user: User, value: str) -> None:
        try:
            HealthProfileService(user).set_fertility_treatment_status(value)
        except Exception:
            self._log_exception("Error saving fertility treatment status")

    @staticmethod
    def _edit_children(old, new):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not old and new:
            # generate id for all new children the 1st time
            for new_child in new:
                new_child["id"] = str(uuid.uuid4())
            return new
        elif new:
            for new_child in new:
                new_child_id = new_child.get("id")
                old_child = next((c for c in old if c["id"] == new_child_id), None)

                if old_child:
                    field_names = ChildSchema().fields.keys()
                    for field_name in field_names:
                        if field_name in new_child:
                            old_child[field_name] = new_child[field_name]
                else:
                    # generate id for new child and add it
                    new_child["id"] = str(uuid.uuid4())
                    old.append(new_child)
            return old

    def _update_mailchimp_subscriber(self, profile, due_date, last_child_birthday):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        kwargs = {}
        new_due_date = profile.due_date
        new_last_child_birthday = profile.last_child_birthday
        if new_due_date != due_date:
            if new_due_date:
                kwargs["due_date"] = new_due_date.strftime("%m/%d/%Y")
            else:
                kwargs["due_date"] = ""
        if new_last_child_birthday != last_child_birthday:
            if new_last_child_birthday:
                kwargs["last_child_birthday"] = new_last_child_birthday.strftime(
                    "%m/%d/%Y"
                )
            else:
                kwargs["last_child_birthday"] = ""
        if kwargs:
            service_ns_tag = "health"
            update_health_profile_in_braze.delay(
                profile.user.id,
                service_ns=service_ns_tag,
                team_ns=service_ns_team_mapper.get(service_ns_tag),
                caller=self.__class__.__name__,
            )


class UserPregnancyAndRelatedConditionsResource(PermissionedCareTeamResource):
    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        target_user = self.target_user(user_id)
        (migration_stage, _) = migration_variation(
            flag_key=MIGRATE_PREGNANCY_DATA_FROM_MONO_TO_HPS,
            context=user_context(self.user),
            default=Stage.OFF,
        )
        if migration_stage == Stage.OFF:
            log.error(
                f"Failed to get pregnancy and related conditions for user {user_id}. "
                f"Pregnancy migration flag is off."
            )
            return make_response("Pregnancy migration flag is off", 500)

        # Step 1: get due_date from mono
        due_date_in_mono = None
        if _should_read_from_mono(migration_stage):
            health_profile = target_user.health_profile
            due_date_in_mono = health_profile.due_date

        # Step 2: get all data from HPS
        release_pregnancy_updates = migration_stage != Stage.OFF
        hps_client = HealthProfileServiceClient(
            user=target_user,
            accessing_user=self.user,
            release_pregnancy_updates=release_pregnancy_updates,
        )
        hps_response: list[
            PregnancyAndRelatedConditions
        ] = hps_client.get_pregnancy_and_related_conditions()

        # Step 3: build and return response
        response_data = self._build_get_response(
            due_date_in_mono, hps_response, migration_stage
        )
        return make_response(response_data, 200)

    def put(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        target_user = self.target_user(user_id)

        (migration_stage, _) = migration_variation(
            flag_key=MIGRATE_PREGNANCY_DATA_FROM_MONO_TO_HPS,
            context=user_context(self.user),
            default=Stage.OFF,
        )
        # Since some pregnancy data are only written to HPS,
        # return early if write to HPS is disabled
        if not _should_write_to_hps(migration_stage):
            return make_response("Write to HPS is disabled", 500)

        request_json = request.json if request.is_json else None
        request_data = None
        try:
            request_data = PutPregnancyAndRelatedConditionsRequestSchema().load(
                request_json
            )
            self._validate_put_request(request_data)
        except ValidationError as e:
            log.error(e.normalized_messages())
            abort(400, error=e.normalized_messages())

        # Step 1: write due_date and first_time_mom of a current pregnancy to mono
        pregnancy = request_data.get("pregnancy")  # type: ignore
        if pregnancy.get("status") == "active" and _should_write_to_mono(
            migration_stage
        ):
            due_date = pregnancy.get("estimated_date")
            first_time_mom = pregnancy.get("is_first_occurrence")
            _update_data_in_mono(target_user, due_date, first_time_mom)

        # Step 2: write all data to HPS
        release_pregnancy_updates = migration_stage != Stage.OFF
        hps_client = HealthProfileServiceClient(
            user=target_user,
            accessing_user=self.user,
            release_pregnancy_updates=release_pregnancy_updates,
        )
        try:
            hps_response = hps_client.put_pregnancy_and_related_conditions(
                pregnancy_and_related_conditions=request_json
            )
            response_data = PregnancyAndRelatedConditionsSchema().dump(hps_response)
            return make_response(response_data, 200)
        except Exception as e:
            # Mono writes are already committed, so we can't do rollback here.
            # For this endpoint, it's okay if mono writes succeeded but HPS writes failed.
            # The reasoning being
            #   - This endpoint is for updating the pregnancy plus related conditions.
            #       Related conditions are only stored in HPS, not in mono.
            #       If the request fails, the user won't be able to see the expected related conditions returned.
            #       As a result, the user will send another request to update the data.
            #   - The data already written in mono will not cause issues,
            #       since mono is still SoT for due_date and first_time_mom.
            log.error("Writes to HPS failed", exception=e)
            abort(500, error=e)

    @staticmethod
    def _build_get_response(
        due_date_in_mono: date | None,
        hps_response: list[PregnancyAndRelatedConditions],
        migration_stage: Stage,
    ) -> list:
        """
        This function builds pregnancy data using
            - mono data
            - HPS data
            - whether mono or HPS is SoT for pregnancy data

        if HPS is SoT,
            return HPS data immediately
        if mono is still SoT,
            if current pregnancy data exists in both in mono and HPS,
                return current pregnancy's due_date and first_time_mom from mono but the rest from HPS
            if current pregnancy data only exists in mono,
                return mono data
        """

        response_data = []

        if _hps_is_source_of_truth_for_read(migration_stage):
            response_data = hps_response
        else:
            if len(hps_response) > 0:
                # When current pregnancy data exists in both mono and HPS,
                # return due_date from mono and the rest from HPS
                for item in hps_response:
                    if item.pregnancy.status == ClinicalStatus.ACTIVE.value:
                        item.pregnancy.estimated_date = due_date_in_mono
                        break
                response_data = hps_response
            elif due_date_in_mono is not None:
                # When current pregnancy data only exists in mono, return mono data
                current_pregnancy = MemberCondition(
                    condition_type=ConditionType.PREGNANCY.value,
                    status=ClinicalStatus.ACTIVE.value,
                    estimated_date=due_date_in_mono,
                )
                current_pregnancy_and_related_conditions = (
                    PregnancyAndRelatedConditions(
                        pregnancy=current_pregnancy, related_conditions={}, alerts={}
                    )
                )
                response_data = [current_pregnancy_and_related_conditions]

        return [
            PregnancyAndRelatedConditionsSchema().dump(item) for item in response_data
        ]

    @staticmethod
    def _validate_put_request(request_data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not request_data.get("pregnancy"):
            abort(400, error="Missing pregnancy")

        pregnancy = request_data.get("pregnancy")
        if not pregnancy.get("status"):
            abort(400, error="Missing status for pregnancy")

        if pregnancy.get("status") == "active":
            if not pregnancy.get("estimated_date"):
                abort(400, error="Missing estimated_date for current pregnancy")
            if pregnancy.get("estimated_date") < datetime.now(tz=pytz.UTC).date():
                abort(
                    400,
                    error="Current pregnancy's estimated_date can't be in the past",
                )
            if pregnancy.get("outcome"):
                abort(400, error="Outcome should not be provided for current pregnancy")

        if pregnancy.get("status") == "resolved":
            if (
                pregnancy.get("abatement_date")
                and pregnancy.get("abatement_date") > datetime.now(tz=pytz.UTC).date()
            ):
                abort(
                    400,
                    error="Past pregnancy's abatement_date can't be in the future",
                )


class PregnancyAndRelatedConditionsResource(PermissionedCareTeamResource):
    def patch(self, pregnancy_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        request_json = request.json if request.is_json else None
        request_data = None
        try:
            request_data = PatchPregnancyAndRelatedConditionsRequestSchema().load(
                request_json
            )
            self._validate_patch_request(request_data)
        except ValidationError as e:
            log.error(e.normalized_messages())
            abort(400, error=e.normalized_messages())

        pregnancy = request_data.get("pregnancy")  # type: ignore
        user_id = pregnancy.get("user_id")  # type: ignore
        target_user = self.target_user(user_id)

        (migration_stage, _) = migration_variation(
            flag_key=MIGRATE_PREGNANCY_DATA_FROM_MONO_TO_HPS,
            context=user_context(self.user),
            default=Stage.OFF,
        )
        # Since some pregnancy data are only written to HPS,
        # return early if write to HPS is disabled
        if not _should_write_to_hps(migration_stage):
            return make_response("Write to HPS is disabled", 500)

        # Step 1: write due_date and first_time_mom of a current pregnancy to mono
        if pregnancy.get("estimated_date") and _should_write_to_mono(migration_stage):
            # update mono data
            due_date = pregnancy["estimated_date"]
            if pregnancy.get("is_first_occurrence") is not None:
                first_time_mom = pregnancy["is_first_occurrence"]
            else:
                first_time_mom = target_user.health_profile.first_time_mom
            _update_data_in_mono(target_user, due_date, first_time_mom)

        # Step 2: write all data to HPS
        release_pregnancy_updates = migration_stage != Stage.OFF
        hps_client = HealthProfileServiceClient(
            user=target_user,
            accessing_user=self.user,
            release_pregnancy_updates=release_pregnancy_updates,
        )
        try:
            hps_response = hps_client.patch_pregnancy_and_related_conditions(
                pregnancy_id=pregnancy_id, pregnancy_and_related_conditions=request_json
            )
            response_data = PregnancyAndRelatedConditionsSchema().dump(hps_response)
            return make_response(response_data, 200)
        except Exception as e:
            # Mono writes are already committed, so we can't do rollback here.
            # For this endpoint, it's okay if mono writes succeeded but HPS writes failed.
            # The reasoning being
            #   - This endpoint is for updating the pregnancy plus related conditions.
            #       Related conditions are only stored in HPS, not in mono.
            #       If the request fails, the user won't be able to see the expected related conditions returned.
            #       As a result, the user will send another request to update the data.
            #   - The data already written in mono will not cause issues,
            #       since mono is still SoT for due_date and first_time_mom.
            log.error("Writes to HPS failed", exception=e)
            abort(500, error=e)

    @staticmethod
    def _validate_patch_request(request_data: dict) -> None:
        if not request_data.get("pregnancy"):
            abort(400, error="Missing pregnancy")

        pregnancy: dict = request_data.get("pregnancy")  # type: ignore
        if not pregnancy.get("user_id"):
            abort(400, error="Missing user_id")

        if (
            pregnancy.get("abatement_date")
            and pregnancy.get("abatement_date") > datetime.now(tz=pytz.UTC).date()
        ):
            abort(
                400,
                error="Past pregnancy's abatement_date can't be in the future",
            )

        if pregnancy.get("estimated_date"):
            if pregnancy.get("estimated_date") < datetime.now(tz=pytz.UTC).date():
                abort(
                    400,
                    error="Current pregnancy's estimated_date can't be in the past",
                )
            if pregnancy.get("outcome"):
                abort(400, error="Outcome should not be set for current pregnancy")


@ddtrace.tracer.wrap()
def _update_data_in_mono(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    user: User,
    due_date: datetime,
    first_time_mom: bool | None = None,
):
    health_profile: HealthProfile = user.health_profile
    existing_due_date = health_profile.due_date
    existing_first_time_mom = health_profile.first_time_mom
    update_due_date = due_date != existing_due_date
    update_first_time_mom = first_time_mom != existing_first_time_mom
    if not update_due_date and not update_first_time_mom:
        return

    if update_due_date:
        health_profile.due_date = due_date
    if update_first_time_mom:
        health_profile.first_time_mom = first_time_mom

    try:
        db.session.add(health_profile)

        # Follow the same logic as PUT and PATCH /v1/users/<int:user_id>/health_profile,
        # where DB transaction is rolled back if the track update fails
        tracks.on_health_profile_update(
            user=user,
            change_reason=ChangeReason.API_PUT_PREGNANCY_AND_RELATED_CONDITIONS,
        )

        db.session.commit()
    except Exception as e:
        log.error("Writes to mono failed", exception=e)
        db.session.rollback()
        abort(500, error=e)

    if update_due_date:
        # update braze
        try:
            service_ns_tag = "health"
            update_health_profile_in_braze.delay(
                health_profile.user.id,
                service_ns=service_ns_tag,
                team_ns=service_ns_team_mapper.get(service_ns_tag),
                caller="_update_data_in_mono",
            )
        except Exception as e:
            log.error("Failed to update health profile in braze", exception=e)

        # update trimester risk flag if due date didn't exist before
        if existing_due_date is None:
            try:
                mr_service = MemberRiskService(
                    user.id,
                    commit=True,
                    modified_by=user.id,
                    modified_reason=ModifiedReason.PREGNANCY_UPDATE,
                )
                mr_service.create_trimester_risk_flags(due_date)
            except Exception as e:
                log.error("Failed to create trimester risk flag", exception=e)


def _should_read_from_mono(migration_stage: Stage) -> bool:
    return migration_stage in [Stage.DUALWRITE, Stage.SHADOW, Stage.LIVE]


def _hps_is_source_of_truth_for_read(migration_stage: Stage) -> bool:
    return migration_stage in [Stage.LIVE, Stage.RAMPDOWN, Stage.COMPLETE]


def _should_write_to_mono(migration_stage: Stage) -> bool:
    return migration_stage != Stage.COMPLETE


def _should_write_to_hps(migration_stage: Stage) -> bool:
    return migration_stage != Stage.OFF
