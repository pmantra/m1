from marshmallow_v1 import Schema, ValidationError, fields

from health.models.health_profile import HealthProfile
from storage.connection import db
from utils.log import logger
from views.profiles import (  # type: ignore[attr-defined] # Module "views.profiles" has no attribute "HealthProfileSchema" #type: ignore[attr-defined] # Module "views.profiles" has no attribute "validate_activity_level" #type: ignore[attr-defined] # Module "views.profiles" has no attribute "validate_life_stages"
    HealthProfileSchema,
    validate_activity_level,
    validate_life_stages,
)
from views.schemas.common import MavenDateTime

log = logger(__name__)


class ChildSchema(Schema):
    id = fields.UUID()
    name = fields.String()
    gender = fields.String()
    birthday = MavenDateTime(default=None)

    class Meta:
        strict = True
        skip_missing = True


class HealthProfileSchema(Schema):  # type: ignore[no-redef] # Name "HealthProfileSchema" already defined (possibly by an import) #type: ignore[no-redef] # Name "HealthProfileSchema" already defined (possibly by an import) # noqa: F811
    """
    Unfortunately I had to redefine the Schema here
    because MavenSchema error handling throws abort(400)
    """

    abortions = fields.Integer()
    activity_level = fields.String(validate=validate_activity_level)
    birthday = MavenDateTime(default=None)
    children = fields.Nested(ChildSchema, many=True)
    due_date = MavenDateTime(default=None)
    fertility_treatment_status = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    food_allergies = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    full_term_babies = fields.Integer()
    gender = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    health_issues_current = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    health_issues_past = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    height = fields.Integer()  # in inches
    insurance = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    life_stage = fields.Integer(validate=validate_life_stages)
    medications_allergies = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    medications_current = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    medications_past = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    miscarriages = fields.Integer()
    number_of_pregnancies = fields.Integer()
    premature_babies = fields.Integer()
    weight = fields.Integer()  # in lbs

    class Meta:
        strict = True
        skip_missing = True


@HealthProfileSchema.validator
def validate_field_types(self, data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Validate fields string and int types.
    The default field validator is too generous to accept raw data.
    This needs to be refactored in the newer version.
    see http://bit.ly/1S8ngpS for version upgrade notes
    :param self: HealthProfileSchema obj instance
    :param data: dict/obj to be converted.
    :raise: ValidationError if type checking fails.
    """
    is_valid = True
    for field_name in self.fields:
        if field_name in data:
            value = data[field_name]
            field = self.fields[field_name]
            if isinstance(field, fields.String) and not isinstance(value, str):
                is_valid = False
                break
            if isinstance(field, fields.Integer) and not isinstance(value, int):
                is_valid = False
                break

    if not is_valid:
        raise ValidationError(f'Invalid "{field_name}" value: {value}', field_name)


def truncate_time(data, field_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if data.get(field_name):
        dt = data[field_name]
        if dt != dt.date():
            return dt.date().isoformat()
        else:
            return dt.isoformat()


# run in console
def cleanup_health_profile():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    hps = HealthProfileSchema()
    profiles = db.session.query(HealthProfile).all()
    for profile in profiles:
        j = profile.json
        if j:
            try:
                hps.validate(j)
                result, errors = hps.load(j)

            except Exception as e:
                log.debug(
                    "HealthProfile %s has invalid field(s): %s; errors=%s",
                    profile.user_id,
                    e,
                    errors,
                )
                continue

            try:
                # truncate datetime fields
                new_birthday = truncate_time(result, "birthday")
                if j.get("birthday") and j["birthday"] != new_birthday:
                    log.debug(
                        "HealthProfile %s birthday truncated from %s to %s",
                        profile.user_id,
                        j["birthday"],
                        new_birthday,
                    )
                    profile.json["birthday"] = new_birthday

                new_due_date = truncate_time(result, "due_date")
                if j.get("due_date") and j["due_date"] != new_due_date:
                    log.debug(
                        "HealthProfile %s due_date truncated from %s to %s",
                        profile.user_id,
                        j["due_date"],
                        new_due_date,
                    )
                    profile.json["due_date"] = new_due_date

                if "children" in result and result["children"]:
                    for (
                        idx,
                        child,  # noqa  B007  TODO:  Loop control variable 'child' not used within the loop body. If this is intended, start the name with an underscore.
                    ) in enumerate(result["children"]):
                        new_child_birthday = truncate_time(
                            result["children"][idx], "birthday"
                        )
                        if j["children"][idx]["birthday"] != new_child_birthday:
                            log.debug(
                                "HealthProfile %s child %s %s's birthday truncated from %s to %s",
                                profile.user_id,
                                idx,
                                j["children"][idx]["name"],
                                j["children"][idx]["birthday"],
                                new_child_birthday,
                            )
                            j["children"][idx]["birthday"] = new_child_birthday
                            profile.json["children"] = j[
                                "children"
                            ]  # trigger dirty flag

                db.session.commit()
            except Exception as e:
                log.debug(
                    "Exception %s occurred while fixing date fields for HealthProfile[%s]. Rolling back...",
                    e,
                    profile.user_id,
                )
                db.session.rollback()
