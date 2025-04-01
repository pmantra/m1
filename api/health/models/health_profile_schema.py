from datetime import date, datetime

from marshmallow import (
    EXCLUDE,
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
    validates,
)

from health.models.health_profile import LIFE_STAGES, HealthProfileActivityLevel
from utils.log import logger
from views.schemas.common_v3 import MavenDateTime

log = logger(__name__)


class ChildSchema(Schema):
    id = fields.UUID()
    name = fields.String()
    gender = fields.String()
    sex_at_birth = fields.String()
    birthday = MavenDateTime()

    @validates("birthday")
    def validate_child_birthday(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # replaces old _validate functionality
        if not value:
            raise ValidationError("Invalid child birthday!")

        # Handling legacy MavenDateTime behavior
        if isinstance(value, datetime):
            if value > datetime.utcnow():
                raise ValidationError("Child birthday should not be in the future!")
        elif isinstance(value, date):
            if value > datetime.utcnow().date():
                raise ValidationError("Child birthday should not be in the future!")
        else:
            raise ValidationError("Invalid child birthday!")


class HealthProfileSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    abortions = fields.Integer(dump_default=None)
    activity_level = fields.String(
        validate=validate.OneOf(
            [
                HealthProfileActivityLevel.__dict__[k]
                for k in HealthProfileActivityLevel.__dict__.keys()
                if not k.startswith("__")
            ],
            error="Invalid activity level: {input}",
        ),
    )
    birthday = MavenDateTime()
    children = fields.List(fields.Nested(ChildSchema))
    # child_auto_added_at field expected from workflows such as an existing P&P/etc member enrolling in postpartum
    child_auto_added_at = MavenDateTime()
    due_date = MavenDateTime()
    fertility_treatment_status = fields.String()
    first_time_mom = fields.Boolean()
    food_allergies = fields.String(dump_default=None)
    full_term_babies = fields.Integer(dump_default=None)
    # to be used as gender identity
    gender = fields.String(dump_default=None)
    # to be used as biological gender
    sex_at_birth = fields.String(dump_default=None)
    health_issues_current = fields.String(dump_default=None)
    health_issues_past = fields.String(dump_default=None)
    height = fields.Integer(dump_default=None)  # in inches
    insurance = fields.String(dump_default=None)
    life_stage = fields.Integer(
        validate=validate.OneOf(
            [stage["id"] for stage in LIFE_STAGES],
            error="Invalid life stages id: {input}",
        ),
    )
    medications_allergies = fields.String(
        dump_default=None,
        validate=validate.Length(
            max=1000,
            error="Please put less than 1000 characters in the free text field.",
        ),
    )
    medications_current = fields.String(
        dump_default=None,
        validate=validate.Length(
            max=1000,
            error="Please put less than 1000 characters in the free text field.",
        ),
    )
    medications_past = fields.String(
        dump_default=None,
        validate=validate.Length(
            max=1000,
            error="Please put less than 1000 characters in the free text field.",
        ),
    )
    miscarriages = fields.Integer(dump_default=None)
    number_of_pregnancies = fields.Integer(dump_default=None)
    premature_babies = fields.Integer(dump_default=None)
    weight = fields.Integer(dump_default=None)  # in lbs
    # these three fields were added from the android app interface contract
    iui_attempts = fields.Integer()
    ivf_attempts = fields.Integer()
    family_medical_history = fields.String(
        validate=validate.Length(
            max=1000,
            error="Please put less than 1000 characters in the free text field.",
        )
    )

    @validates("birthday")
    def validate_date_or_datetime(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # Handling legacy MavenDateTime behavior
        if isinstance(value, datetime):
            if value > datetime.utcnow():
                raise ValidationError("Your birthday should be in the past!")
        elif isinstance(value, date):
            if value > datetime.utcnow().date():
                raise ValidationError("Your birthday should be in the past!")

    @pre_load(pass_many=True)
    def health_profile_backwards_compatibility(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # covering old _filter_values typo correction functionality
        if "miscarrages" in data:
            data["miscarriages"] = data["miscarrages"]
            del data["miscarrages"]

        # covering bug where FE would send the due_date in the display format with slashes.
        if "due_date" in data:
            try:
                data["due_date"] = (
                    datetime.strptime(data["due_date"], "%m/%d/%Y").date().isoformat()
                )
                # catch and ignore exceptions for this and let them be handled in validation-proper
            except ValueError:
                pass
            except TypeError:
                pass

        # covering old _filter_values, backwards compatibility test functionality
        return {
            key: value
            for key, value in data.items()
            if value is not None and value != ""
        }
