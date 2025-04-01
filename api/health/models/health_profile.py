import datetime
import json
import traceback
import uuid
from datetime import timedelta
from typing import Any, List, Optional, Union

from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from sqlalchemy import Column, Date, Float, ForeignKey, Integer, Text, event
from sqlalchemy.orm import relationship

from models import base
from models.base import (
    BoolJSONProperty,
    DateJSONProperty,
    IntJSONProperty,
    StringJSONProperty,
    db,
)
from utils.age import calculate_age
from utils.data import JSONAlchemy
from utils.log import logger

log = logger(__name__)


FERTILITY_TREATMENT_STATUS = (
    "preconception",
    "considering_fertility_treatment",
    "undergoing_iui",
    "undergoing_ivf",
    "successful_pregnancy",
    "other",
)


LIFE_STAGES = [
    {
        "id": 1,
        "weight": 1,
        "image": "life-stage-1",
        "name": "pregnant",
        "subtitle": "",
        "title": "I'm Pregnant",
    },
    {
        "id": 2,
        "weight": 2,
        "image": "life-stage-2",
        "name": "new-mom",
        "subtitle": "With a baby under 24 months",
        "title": "I'm A New Mom",
    },
]


class HealthProfileHelpers:
    # https://docs.sqlalchemy.org/en/14/core/defaults.html#context-sensitive-default-functions

    @staticmethod
    def dump_to_json_with_date(json_object) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        def serialize_date(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            if isinstance(obj, (datetime.date, datetime.datetime)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        return json.dumps(json_object, default=serialize_date)

    @classmethod
    def parse_children_birthdays(cls, children, with_age_repr: bool = False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        processable = []
        for child in children:
            try:
                new_child_dict = {"birthday": parse(child.get("birthday")).date()}
            except (ValueError, TypeError):
                log.debug(f"Could not process: {child}")
                log.error("Could not parse child's birthday.")
            else:
                if child.get("id"):
                    new_child_dict["id"] = child.get("id")
                if child.get("name"):
                    new_child_dict["name"] = child.get("name")
                if with_age_repr:
                    age = cls.child_age_repr(new_child_dict["birthday"])
                    if age:
                        new_child_dict["age"] = age
                processable.append(new_child_dict)
        return processable

    @staticmethod
    def get_json_from_context(context) -> dict:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        context_params = context.get_current_parameters() if context else {}
        return context_params.get("json", {})

    @classmethod
    def get_children_from_context(cls, context) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        json_obj = cls.get_json_from_context(context)
        children = cls.get_children_from_json(json_obj)
        return cls.dump_to_json_with_date(children)

    @classmethod
    def get_children_from_json(cls, input_json) -> List[dict]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        children = input_json.get("children", []) or []
        return children

    @classmethod
    def get_bmi_from_context(cls, context) -> Optional[float]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        json_obj = cls.get_json_from_context(context)
        return cls.get_bmi_from_json(json_obj)

    @classmethod
    def get_bmi_from_json(cls, input_json) -> Optional[float]:  # type: ignore[return,no-untyped-def] # Missing return statement #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        height = input_json.get("height")
        weight = input_json.get("weight")
        try:
            height = int(height)
        except (ValueError, TypeError):
            height = None

        try:
            weight = int(weight)
        except (ValueError, TypeError):
            weight = None

        if height and weight:
            return 703 * weight / height**2

    @classmethod
    def get_age_from_context(cls, context) -> Optional[int]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        json_obj = cls.get_json_from_context(context)
        return cls.get_age_from_json(json_obj)

    @classmethod
    def get_age_from_json(cls, input_json) -> Optional[int]:  # type: ignore[return,no-untyped-def] # Missing return statement #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        birthday = input_json.get("birthday")
        try:
            birthday = parse(birthday).date() if birthday else None
        except ValueError:
            birthday = None
        if birthday:
            if not isinstance(birthday, datetime.date):
                log.debug(
                    "Can not parse birthday as date",
                    birthday=birthday,
                    birthday_type=type(birthday),
                )
                return  # type: ignore[return-value] # Return value expected
            _age = calculate_age(birthday)  # type: ignore[arg-type] # Argument 1 to "calculate_age" has incompatible type "date"; expected "datetime"

            if _age <= 0:
                log.debug(
                    "Invalid birthday in health profile", age=_age, birthday=birthday
                )
                return  # type: ignore[return-value] # Return value expected

            return _age

    @classmethod
    def get_children_with_age_from_json(cls, input_json):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        children_list = cls.get_children_from_json(input_json=input_json)
        sorted_children = sorted(
            HealthProfileHelpers.parse_children_birthdays(
                children=children_list, with_age_repr=True
            ),
            key=lambda c: c["birthday"],
            reverse=True,
        )
        return sorted_children

    @classmethod
    def get_children_with_age_from_context(cls, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        json_obj = cls.get_json_from_context(context)
        children_object = cls.get_children_with_age_from_json(json_obj)
        return cls.dump_to_json_with_date(children_object)

    @staticmethod
    def child_age_repr(birthday: datetime.date):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        today = datetime.date.today()
        if birthday > today:
            log.debug("Cannot determine age of child with birthday in the future.")
            return
        age = relativedelta(today, birthday)
        if age.years >= 10:
            return f"{age.years} y"
        if age.years >= 2:
            return f"{age.years} y, {age.months} m"
        total_months = age.years * 12 + age.months
        if total_months >= 2:
            return f"{total_months} m"
        absolute_age = today - birthday
        total_weeks = int(absolute_age.days / 7)
        if total_weeks >= 2:
            return f"{total_weeks} w"
        return f"{absolute_age.days} d"

    @classmethod
    def get_last_child_birthday_from_json(cls, input_json) -> datetime.date:  # type: ignore[return,no-untyped-def] # Missing return statement #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        childen_list = cls.get_children_from_json(input_json=input_json)
        processable = HealthProfileHelpers.parse_children_birthdays(childen_list)

        if processable:
            return max(p["birthday"] for p in processable)

    @classmethod
    def get_last_child_birthday_from_context(cls, context) -> datetime.date:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        json_obj = cls.get_json_from_context(context)
        return cls.get_last_child_birthday_from_json(json_obj)


def _parse_birthday(birthday_value: Any) -> datetime.date:
    """Utility function to handle various birthday formats.

    Args:
        birthday_value (Any): The birthday value, which could be a string, datetime, or date.

    Returns:
        date: Parsed date in `datetime.date` format.

    Raises:
        ValueError: If the birthday_value is an unsupported format.
    """
    if isinstance(birthday_value, str):
        # Parse string to datetime.date
        return datetime.datetime.strptime(birthday_value, "%Y-%m-%d").date()
    elif isinstance(birthday_value, datetime.datetime):
        # Convert datetime.datetime to datetime.date
        return birthday_value.date()
    elif isinstance(birthday_value, datetime.date):
        # Already a datetime.date
        return birthday_value
    else:
        raise ValueError(f"Unsupported date format: {birthday_value}")


class HealthProfile(base.TimeLoggedModelBase):
    """
    User's healthcare related information.
    """

    __tablename__ = "health_profile"
    __calculated_columns__ = frozenset(
        ["children", "children_with_age", "bmi", "age", "last_child_birthday"]
    )

    user_id = Column(Integer, ForeignKey("user.id"), primary_key=True)
    user = relationship(
        "User",
        back_populates="health_profile",
        uselist=False,
        # TODO: `" "delete` is not a valid cascade option. What has this been behaving like?
        # cascade="save-update, merge, " "delete, delete-orphan",
    )
    json = Column(JSONAlchemy(Text()), default={})
    date_of_birth = Column(Date, nullable=True, default=None)

    due_date = DateJSONProperty("due_date")
    birthday = DateJSONProperty("birthday")

    height = IntJSONProperty("height")
    weight = IntJSONProperty("weight")

    # be aware that racial_identity is not a complete export from HDC
    # In order to build a fast solution for risk calculation, only one ethnicity is exported to
    # health_profile. If there are multiple ethnicity, the one with the higher priority is picked.
    # see how ethnicity impacts risk calculation in the product brief
    # https://docs.google.com/document/d/1bKYMsNAD8G_FPRa1Hb1H4gomBTk-0A4-6J89WLgg8r4/edit?tab=t.0
    # for a long term solution, please reference the 'blocked by' tickets linked to MPC-4449
    # https://mavenclinic.atlassian.net/browse/MPC-4449
    racial_identity = StringJSONProperty("racial_identity", nullable=True)

    bmi_persisted = Column(
        Float,
        default=HealthProfileHelpers.get_bmi_from_context,
        onupdate=HealthProfileHelpers.get_bmi_from_context,
    )
    age_persisted = Column(
        Integer,
        default=HealthProfileHelpers.get_age_from_context,
        onupdate=HealthProfileHelpers.get_age_from_context,
    )

    children_persisted = Column(
        Text,
        default=HealthProfileHelpers.get_children_from_context,
        onupdate=HealthProfileHelpers.get_children_from_context,
    )

    children_with_age_persisted = Column(
        Text,
        default=HealthProfileHelpers.get_children_with_age_from_context,
        onupdate=HealthProfileHelpers.get_children_with_age_from_context,
    )

    last_child_birthday_persisted = Column(
        Date,
        default=HealthProfileHelpers.get_last_child_birthday_from_context,
        onupdate=HealthProfileHelpers.get_last_child_birthday_from_context,
    )

    first_time_mom = BoolJSONProperty("first_time_mom")

    def __repr__(self) -> str:
        return f"<HealthProfile [{self.user_id}]>"

    __str__ = __repr__

    # Dynamic properties are used here for data that is access before any commit is made to the database
    # The corresponding persisted columns will be used for historical tracking and will be updated only
    # after a commit
    @property
    def children(self) -> List[dict]:
        return HealthProfileHelpers.get_children_from_json(self.json or {})

    @property
    def children_with_age(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return HealthProfileHelpers.get_children_with_age_from_json(self.json or {})

    @property
    def bmi(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return HealthProfileHelpers.get_bmi_from_json(self.json or {})

    @property
    def age(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return HealthProfileHelpers.get_age_from_json(self.json or {})

    @property
    def last_child_birthday(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return HealthProfileHelpers.get_last_child_birthday_from_json(self.json)

    def update_children(self, new_children: List[dict]) -> None:
        """Update the 'children' part of the JSON data."""
        sorted_children = sorted(
            new_children, key=lambda x: _parse_birthday(x["birthday"])
        )
        self.json["children"] = sorted_children

    def search_children_by_birthday_range(self, birthday_start, birthday_end):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Search matching children based on birthday range.
        :param birthday_start: date type, the start of birthday range
        :param birthday_end: date type, the end of birthday range
        :return: list of matching children
        """
        matches = []
        assert isinstance(birthday_start, datetime.date)
        assert isinstance(birthday_end, datetime.date)
        assert birthday_start < birthday_end

        children = HealthProfileHelpers.parse_children_birthdays(self.children)
        for child in children:
            if birthday_start <= child.get("birthday") <= birthday_end:
                # convert back to str to be JSON serializable
                child["birthday"] = str(child.get("birthday"))
                matches.append(child)

        log.debug(f"Found {len(matches)} children with matching birthdays in range")
        return matches

    # TODO: This function is inaccurate and should be replaced with `add_or_update_a_child`.
    # `add_a_child` only checks for conflicts with the immediately previous child, rather than
    # verifying conflicts with all existing children.
    def add_a_child(
        self,
        birthday: Union[str, datetime.datetime, datetime.date],
        name: Optional[str] = None,
    ) -> None:
        children = self.children
        child_id = str(uuid.uuid4())
        if not name:
            name = f"Child {len(children) + 1}"

        try:
            if isinstance(birthday, datetime.datetime):
                birthday = birthday.date()
            elif not isinstance(birthday, datetime.date):
                birthday = parse(birthday).date()
        except Exception as e:
            log.error(
                "Invalid Child Birthday",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            return
        if self._try_update_auto_added_child(birthday, name):
            return

        children.append({"id": child_id, "name": name, "birthday": str(birthday)})
        if self.json is None:
            self.json = {}
        self.json["children"] = children
        self.json["child_auto_added_at"] = datetime.datetime.utcnow().isoformat()

    def add_child_using_due_date(self) -> None:
        child_birthday: Optional[datetime.date] = self.due_date
        if not child_birthday:
            return
        name = "Automatically Added"
        self.add_a_child(child_birthday, name)

    def _try_update_auto_added_child(self, birthday: datetime.date, name: str) -> bool:
        try:
            # During Pregnancy -> Postpartum Track Auto-Transition, a child gets added
            # When the Member then fills out the Transition Assessment, another child gets added
            # We want to replace the auto-added child with the manually entered one
            # Assumptions:
            #   Auto-added child has name "Automatically Added"
            #   Only attempt to edit the last child
            #      This should be the typical case.
            #      We don't want to make any complicated guesses/merges
            #   Only edit if the auto-added child birthday is within 60 days of the new child's birthday
            children: List = self.children
            if not children:
                return False
            last_child = children[-1]
            if not last_child:
                return False
            if last_child.get("name", "") != "Automatically Added":
                return False
            delta = parse(last_child["birthday"]).date() - birthday
            if abs(delta.days) <= 60:
                last_child["birthday"] = str(birthday)
                last_child["name"] = name
                self.json["children"] = children
                return True
        except Exception as e:
            log.error(
                "Error attempting to modify auto-added child",
                error=str(e),
                traceback=traceback.format_exc(),
            )
        return False

    def add_or_update_a_child(
        self,
        birthday: Union[str, datetime.datetime, datetime.date],
        name: Union[str, None] = None,
        child_id: Union[str, None] = None,
    ) -> bool:
        """Attempts to add or update a child entry in self.children.

        Args:
            birthday (Union[str, datetime, date]): The birthday of the child to add or update.
            name (str): The name of the child to add or update.
            child_id (Union[str, None] ): id of the child to add or update.

        Returns:
            bool: True if a child was successfully added or updated, False otherwise.
        """
        try:
            # Parse birthday to ensure it's in datetime.date format
            birthday = _parse_birthday(birthday)

            # Sort children by birthday, handling various formats
            children = self.children

            # Define time window for birthday conflict (±60 days)
            conflict_window = timedelta(days=60)

            child_id = child_id or str(uuid.uuid4())

            name = name or f"Child {len(children) + 1}"

            # Check if the child to add has name "Automatically Added"
            if name == "Automatically Added" or name == "Manual":
                # Only add if no other child's birthday is within ±60 days
                for child in children:
                    existing_birthday = _parse_birthday(child["birthday"])
                    if abs((existing_birthday - birthday).days) <= conflict_window.days:
                        # Found a conflict, don't add this child
                        return False

                # No conflicts, safe to add
                children.append(
                    {"id": child_id, "name": name, "birthday": str(birthday)}
                )
                self.update_children(children)  # Update the json
                return True
            else:
                # Check for conflicts with "Automatically Added" children
                for child in children:
                    if (
                        child.get("name") == "Automatically Added"
                        or child.get("name") == "Manual"
                    ):
                        existing_birthday = _parse_birthday(child["birthday"])
                        if (
                            abs((existing_birthday - birthday).days)
                            <= conflict_window.days
                        ):
                            # Conflict found, update this "Automatically Added" child
                            child["name"] = name
                            child["birthday"] = str(birthday)
                            self.update_children(children)  # Update the json
                            return True

                # No "Automatically Added" conflicts, add this new child as normal
                children.append(
                    {"id": child_id, "name": name, "birthday": str(birthday)}
                )
                self.update_children(children)  # Update the json
                return True
        except Exception as e:
            log.error(
                "Error attempting to add or update child",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            return False


class HealthProfileActivityLevel:
    """
    Derived from iOS repo Maven/_SOURCE/_COMMON/_MODELS/HealthBinder.swift
    Consolidated the data structure definition on the backend
    since eventually we will have web/android as well.
    """

    not_set = ""
    not_active = "NOT ACTIVE"
    fairly_active = "FAIRLY ACTIVE"
    active = "ACTIVE"
    super_active = "SUPER ACTIVE"


# todo this should be moved out of this file, and somewhere that does not create circular dependency
def set_risks_for_health_profile_change(mapper, connection, target: HealthProfile):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    from health.models.risk_enums import RiskInputKey
    from health.services.member_risk_service import MemberRiskService

    if target is None or not target.json:
        return
    updated_values = {}
    # We don't know if these values actually changed or not
    if target.age:
        updated_values[RiskInputKey.AGE] = target.age
    if target.weight:
        updated_values[RiskInputKey.WEIGHT_LB] = target.weight
    if target.height:
        updated_values[RiskInputKey.HEIGHT_IN] = target.height
    if target.racial_identity:
        updated_values[RiskInputKey.RACIAL_IDENTITY] = target.racial_identity

    # Don't run the Member Risk Calculations if they are all None as it will be a no-op
    if not updated_values:
        return
    modified_by = None  # is there a way to get the logged-in user?
    modified_reason = "Health Profile Save"
    with db.session.no_autoflush:
        service = MemberRiskService(
            target.user_id,
            commit=False,
            write_using_execute=True,
            modified_by=modified_by,
            modified_reason=modified_reason,
            health_profile=target,
        )
        service.calculate_risks(updated_values)


event.listen(HealthProfile, "after_update", set_risks_for_health_profile_change)
event.listen(HealthProfile, "after_insert", set_risks_for_health_profile_change)
