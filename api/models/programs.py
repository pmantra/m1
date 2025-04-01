import datetime
import enum
import functools
from typing import TYPE_CHECKING, Optional, Union

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    bindparam,
    case,
    event,
    select,
)
from sqlalchemy.ext import baked
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (
    Query,
    backref,
    column_property,
    contains_eager,
    relationship,
    validates,
)
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import exists

from health.models.health_profile import HealthProfile
from models.base import TimeLoggedModelBase, db
from models.enterprise import OrganizationModuleExtension
from utils.data import JSONAlchemy
from utils.exceptions import (
    DueDateRequiredError,
    InvalidPhaseTransitionError,
    LastChildBirthdayRequiredError,
    ModuleConfigurationError,
    ModuleUserStateError,
    ScheduledEndOutOfRangeError,
)
from utils.log import logger

if TYPE_CHECKING:
    from authn.models.user import User

log = logger(__name__)
bakery = baked.bakery()  # type: ignore[call-arg,func-returns-value] # Missing positional argument "initial_fn" in call to "__call__" of "Bakery" #type: ignore[func-returns-value] # Function does not return a value (it only ever returns None) #type: ignore[func-returns-value] # Function does not return a value (it only ever returns None)


_DAYS_IN_PREGNANCY = 280
_POSTPARTUM_PERIOD = datetime.timedelta(days=168)


@enum.unique
class PhaseLogic(enum.Enum):
    """The logic used to determine entry and current program phases for the module."""

    STATIC = "STATIC"
    WEEKLY = "WEEKLY"
    DUE_DATE = "DUE_DATE"
    CHILD_BIRTH = "CHILD_BIRTH"


def _weekly_phase_at(error_class, module, entry, days):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    week_number = int(days / 7)
    phase_name = f"week-{week_number}"
    try:
        phase = (
            db.session.query(Phase)
            .join(Phase.module)
            .filter(Phase.module == module, Phase.name == phase_name)
            .one()
        )
    except NoResultFound:
        msg = f"No phase defined in module {module} for week number {week_number}."
        raise error_class(msg)

    if entry and not phase.is_entry:
        msg = f"Module {module} defines week number {week_number}, but it cannot be used as an entry phase."
        raise error_class(msg)

    return phase


def _phase_logic_static(module, _entry, _user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """places the user in the entry phase."""
    entry_phases = [p for p in module.phases if p.is_entry]
    if len(entry_phases) == 1:
        return entry_phases[0]
    msg = (
        f"Module {module} with static phase logic should have exactly one entry phase."
    )
    raise ModuleConfigurationError(msg)


def _phase_logic_weekly_module_start(module, entry, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """places the user in week-1, week-2, etc. according to module start date."""
    if entry:
        # Let the user enter this module at week one.
        return _weekly_phase_at(ModuleConfigurationError, module, entry, 7)
    current = user.current_program
    if not current:
        msg = f"Cannot determine phase of module {module} for user {user} without current program."
        raise ModuleUserStateError(msg)
    module_start = current and current.module_started_at(module.name)
    if not module_start:
        msg = f"Cannot determine phase of module {module} for program {current} without module start date."
        raise ModuleUserStateError(msg)
    today = datetime.datetime.utcnow().date()
    days = (today - module_start.date()).days
    return _weekly_phase_at(
        ModuleUserStateError, module, entry, days + 7
    )  # start from week-1 rather than week-0


def _phase_logic_due_date(module, entry, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Places the user in a weekly phase according to due date."""
    today = datetime.datetime.utcnow().date()
    try:
        days_until_due = (user.health_profile.due_date - today).days
    except (AttributeError, TypeError):
        msg = f"Cannot determine phase of module {module} for user {user} without due_date."
        raise DueDateRequiredError(msg)
    days = _DAYS_IN_PREGNANCY - days_until_due
    return _weekly_phase_at(DueDateRequiredError, module, entry, days)


def _phase_logic_child_birth(module, entry, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Places the user in a weekly phase according to last child birthday."""
    today = datetime.datetime.utcnow().date()
    try:
        days_after_birth = (today - user.health_profile.last_child_birthday).days
    except (AttributeError, TypeError):
        msg = f"Cannot determine phase of module {module} for user {user} without last_child_birthday."
        raise LastChildBirthdayRequiredError(msg)
    days = _DAYS_IN_PREGNANCY + days_after_birth
    return _weekly_phase_at(LastChildBirthdayRequiredError, module, entry, days)


_PHASE_LOGIC_REGISTRY = {
    PhaseLogic.STATIC: _phase_logic_static,
    PhaseLogic.WEEKLY: _phase_logic_weekly_module_start,
    PhaseLogic.DUE_DATE: _phase_logic_due_date,
    PhaseLogic.CHILD_BIRTH: _phase_logic_child_birth,
}
assert all(v in _PHASE_LOGIC_REGISTRY for v in PhaseLogic)
_PHASE_LOGIC_DOC = "\n".join(
    [str(PhaseLogic.__doc__), ""]
    + [f"{k.value}: {v.__doc__}" for k, v in _PHASE_LOGIC_REGISTRY.items() if v.__doc__]
)


def _auto_transition_no_op(_module, _user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    pass


def _auto_transition_child_birth(module, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if _has_valid_entry_child_birth(module, user):
        log.debug(
            f"Using existing child birthday in auto transition into module {module} for user {user}."
        )
        return

    try:
        hp: HealthProfile = user.health_profile
        log.debug(
            f"Adding fake child in auto transition into module {module} for user {user}."
        )
        hp.add_child_using_due_date()
    except AttributeError:
        msg = f"Cannot determine child birthday in auto transition into module {module} for user {user}."
        raise DueDateRequiredError(msg)


def _has_valid_entry_child_birth(module, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        _phase_logic_child_birth(module, True, user)
        return True
    except LastChildBirthdayRequiredError:
        return False


_AUTO_TRANSITION_NOT_IMPLEMENTED_REGISTRY = {PhaseLogic.DUE_DATE}
_AUTO_TRANSITION_REGISTRY = {
    PhaseLogic.STATIC: _auto_transition_no_op,
    PhaseLogic.WEEKLY: _auto_transition_no_op,
    PhaseLogic.CHILD_BIRTH: _auto_transition_child_birth,
}
assert all(
    v in _AUTO_TRANSITION_NOT_IMPLEMENTED_REGISTRY or v in _AUTO_TRANSITION_REGISTRY
    for v in PhaseLogic
)


@enum.unique
class ProgramLengthLogic(enum.Enum):
    """The logic used to determine the program length for the module."""

    UNLIMITED = "UNLIMITED"
    DURATION = "DURATION"
    DUE_DATE = "DUE_DATE"
    CHILD_BIRTH = "CHILD_BIRTH"


def _program_length_logic_unlimited(_module, _user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Program never ends."""
    return


def _program_length_logic_duration(module, _user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Program ends `duration` days from today."""
    try:
        today = datetime.datetime.utcnow().date()
        return today + datetime.timedelta(days=module.duration)
    except TypeError:
        msg = f"Cannot schedule end of program in module {module} without a module duration."
        raise ModuleConfigurationError(msg)


def _program_length_logic_due_date(module, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Program ends 168 days after due date."""
    try:
        return user.health_profile.due_date + _POSTPARTUM_PERIOD
    except (AttributeError, TypeError):
        msg = f"Cannot schedule end of program in module {module} for user {user} without due_date."
        raise DueDateRequiredError(msg)


def _program_length_logic_child_birth(module, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Program ends 168 days after last child birthday."""
    try:
        return user.health_profile.last_child_birthday + datetime.timedelta(
            days=module.duration
        )
    except (AttributeError, TypeError):
        msg = f"Cannot schedule end of program in module {module} for user {user} without last_child_birthday."
        raise LastChildBirthdayRequiredError(msg)


_PROGRAM_LENGTH_LOGIC_REGISTRY = {
    ProgramLengthLogic.UNLIMITED: _program_length_logic_unlimited,
    ProgramLengthLogic.DURATION: _program_length_logic_duration,
    ProgramLengthLogic.DUE_DATE: _program_length_logic_due_date,
    ProgramLengthLogic.CHILD_BIRTH: _program_length_logic_child_birth,
}
assert all(v in _PROGRAM_LENGTH_LOGIC_REGISTRY for v in ProgramLengthLogic)
_PROGRAM_LENGTH_LOGIC_DOC = "\n".join(
    [str(ProgramLengthLogic.__doc__), ""]
    + [
        f"{k.value}: {v.__doc__}"
        for k, v in _PROGRAM_LENGTH_LOGIC_REGISTRY.items()
        if v.__doc__
    ]
)


# TODO: [Tracks] remove this once the Tracks migration is complete.
# This enum is duplicated in api/models/tracks/track.py to avoid
# 1) an import cycle 2) dependency on programs.py specifically.
@enum.unique
class ModuleRequiredInformation(str, enum.Enum):
    DUE_DATE = "DUE_DATE"
    CHILD_BIRTH = "CHILD_BIRTH"


module_vertical_groups = db.Table(
    "module_vertical_groups",
    Column("module_id", Integer, ForeignKey("module.id"), nullable=False),
    Column(
        "vertical_group_id", Integer, ForeignKey("vertical_group.id"), nullable=False
    ),
    UniqueConstraint("module_id", "vertical_group_id"),
)


class Module(TimeLoggedModelBase):
    __tablename__ = "module"

    id = Column(Integer, primary_key=True)
    name = Column(String(140), nullable=False, doc="The logical name of the module.")
    frontend_name = Column(
        String(140),
        nullable=True,
        doc="User facing copy describing which program this module belongs to.",
    )
    phase_logic = Column(
        Enum(PhaseLogic, native_enum=False), nullable=False, doc=_PHASE_LOGIC_DOC
    )
    program_length_logic = Column(
        Enum(ProgramLengthLogic, native_enum=False),
        nullable=False,
        doc=_PROGRAM_LENGTH_LOGIC_DOC,
    )
    days_in_transition = Column(
        Integer,
        default=None,
        nullable=True,
        doc="The number of days leading up to program scheduled end in which user is moved to the transitional phase. "
        "This duration is added on top of program length when establishing program scheduled end.",
    )
    duration = Column(
        Integer,
        default=None,
        nullable=True,
        doc=f"The program length in days when program length logic is set to {ProgramLengthLogic.DURATION.value}.",
    )
    allow_phase_browsing = Column(Boolean, default=True, nullable=False)  # Deprecated
    is_maternity = Column(Boolean, nullable=True)
    restrict_booking_verticals = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Restrict bookings to the verticals defined in this module's 'vertical groups'",
    )
    json = Column(JSONAlchemy(Text), default={})
    partner_module_id = Column(Integer, ForeignKey("module.id"), nullable=True)
    _partner_module = relationship(
        "Module",
        remote_side=[id],
        post_update=True,
        backref=backref("_partner_module_backref", uselist=False, post_update=True),
    )

    intro_message_text_copy_id = Column(
        Integer, ForeignKey("text_copy.id"), nullable=True
    )
    intro_message_text_copy = relationship(
        "TextCopy",
        backref=backref("modules_using_copy"),
        doc=(
            "The text copy to use when sending the initial CX message for this module. "
            "If not set, no message will be sent to users who do not book their intro appt in 3 hours."
        ),
    )

    onboarding_as_partner = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Members onboarding into this module are the partner of the person primarily receiving care.",
    )
    onboarding_display_label = Column(
        String(191),
        nullable=True,
        doc="The text copy used to describe this module to members during enterprise onboarding.",
    )
    onboarding_display_order = Column(
        Integer,
        default=None,
        nullable=True,
        doc="The order in which this module will be displayed to members during enterprise onboarding.",
    )

    vertical_groups = relationship(
        "VerticalGroup",
        backref="modules",
        secondary=module_vertical_groups,
        doc="The vertical groups that will show up during booking flow. If 'restrict_booking_verticals' is checked, booking flow search results will also be limited to these verticals",
    )

    def __repr__(self) -> str:
        return f"<Module[{self.id}] {self.name}>"

    __str__ = __repr__

    @property
    def number_of_phases(self) -> int:
        return len(self.phases)

    @property
    def admin_module_configured(self) -> str:
        errors = list(self.module_configuration_errors)
        if errors:
            return " \u2022 ".join(f"\u2717 {e}" for e in errors)
        return "\u2713"

    @property
    def module_configuration_errors(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        transitional_phases = [p for p in self.phases if p.is_transitional]
        entry_phases = [p for p in self.phases if p.is_entry]

        if self.days_in_transition:
            if len(transitional_phases) != 1:
                yield "modules with days_in_transition should have exactly one transitional phase"
            if self.days_in_transition <= 0:
                yield "days_in_transition should be a positive number"
        elif transitional_phases:
            yield "modules with no days_in_transition should not have a transitional phase"

        if self.phase_logic == PhaseLogic.STATIC:
            if len(entry_phases) != 1:
                yield "modules with static phase logic should have exactly one entry phase"
            elif entry_phases[0].name != self.name:
                yield "modules with static phase logic expect their entry phase to have the same name"
        elif self.phase_logic in (
            PhaseLogic.DUE_DATE,
            PhaseLogic.CHILD_BIRTH,
            PhaseLogic.WEEKLY,
        ):
            if not entry_phases:
                yield "weekly phase logic modules should have at least one entry phase"

            week_prefix = "week-"
            for p in self.phases:
                if p.is_transitional:
                    continue
                if (
                    not p.is_entry and p.name == self.name
                ):  # ignore deactivated static entry phases
                    continue
                try:
                    if not p.name.startswith(week_prefix):
                        raise ValueError()
                    number_str = p.name[len(week_prefix) :]
                    number = int(number_str)
                    if number < 0:
                        raise ValueError()
                    if str(number) != number_str:
                        raise ValueError()
                except (TypeError, ValueError):
                    yield f'non-transitional phase {p} should have a name in the form "week-[number]"'

        if self.program_length_logic in (
            ProgramLengthLogic.DURATION,
            ProgramLengthLogic.CHILD_BIRTH,
        ):
            if not self.duration or self.duration <= 0:
                yield "modules with duration program length logic should have a positive duration"
            if (
                self.program_length_logic == ProgramLengthLogic.DURATION
                and not self.days_in_transition
            ):
                yield "modules with duration program length logic should define days in transition"
        elif self.duration:
            yield "modules with non-duration program length logic should not have a duration"

        if self.onboarding_as_partner:
            if not self.partner_module:
                yield "modules with onboarding as partner set to true must have a partner module defined."
            elif self.partner_module.onboarding_as_partner:
                yield 'only one of a pair of partner modules may be marked "onboarding as partner".'

    @property
    def display_name(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.frontend_name or self.name

    @property
    def partner_module(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self._partner_module or self._partner_module_backref

    @partner_module.setter
    def partner_module(self, new_partner):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        assert self != new_partner, "A module cannot be its own partner module."
        # self can no longer be another module's partner
        self._partner_module_backref = None
        if new_partner is None:
            self._partner_module = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type Module)
        else:
            # new_partner can no longer be another module's partner
            new_partner._partner_module_backref = None
            self._partner_module = new_partner
            new_partner._partner_module = self

    @property
    def transitional_phase(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        transitional_phases = [p for p in self.phases if p.is_transitional]
        if len(transitional_phases) == 1:
            return transitional_phases[0]

        if len(transitional_phases) > 1:
            raise ValueError("More than one transitional phase has been configured.")

        raise ValueError("Please select which phase should be the transitional phase.")

    @property
    def required_information(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        required = []
        if (
            self.phase_logic == PhaseLogic.DUE_DATE
            or self.program_length_logic == ProgramLengthLogic.DUE_DATE
        ):
            required.append(ModuleRequiredInformation.DUE_DATE)
        if (
            self.phase_logic == PhaseLogic.CHILD_BIRTH
            or self.program_length_logic == ProgramLengthLogic.CHILD_BIRTH
        ):
            required.append(ModuleRequiredInformation.CHILD_BIRTH)
        return required

    def get_current_phase_for(self, user, scheduled_end):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Determine the current time-based phase for the given user in this module leading up to a scheduled end."""

        if scheduled_end and self.days_in_transition:
            today = datetime.datetime.utcnow().date()
            transition_start = scheduled_end - datetime.timedelta(
                days=self.days_in_transition
            )
            if transition_start <= today <= scheduled_end:
                return self.transitional_phase

        return _PHASE_LOGIC_REGISTRY[self.phase_logic](self, False, user)  # type: ignore[index] # Invalid index type "str" for "Dict[PhaseLogic, Callable[[Any, Any, Any], Any]]"; expected type "PhaseLogic"

    def get_entry_phase_for(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Determine which phase the given user should enter when transitioning into this module."""
        return _PHASE_LOGIC_REGISTRY[self.phase_logic](self, True, user)  # type: ignore[index] # Invalid index type "str" for "Dict[PhaseLogic, Callable[[Any, Any, Any], Any]]"; expected type "PhaseLogic"

    def get_scheduled_end_for(self, user, extension):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Determine when the given user is expected to end a program in this module including normal transitions.

        Scheduled end should be understood as our best estimate of when the user will complete
        every module within this program. For example, a user entering pregnancy will have a scheduled
        end reflecting the end of their postpartum module. However, during module transitions scheduled
        end is updated, and as such will reflect the reality as it unfolds. Examples including updated
        health information, or a user actually experiencing a transition into loss.
        """
        end = _PROGRAM_LENGTH_LOGIC_REGISTRY[self.program_length_logic](self, user)  # type: ignore[index] # Invalid index type "str" for "Dict[ProgramLengthLogic, Callable[[Any, Any], Any]]"; expected type "ProgramLengthLogic"
        if not end:
            log.debug(
                "Determined unlimited scheduled end of module %s for user %s.",
                self,
                user,
            )
            return

        if extension:
            end += datetime.timedelta(days=extension.extension_days)

        if end <= datetime.date.today():
            log.debug(
                "Refusing to schedule end of program resulting in user being in or after the transitional period.",
                module_id=self.id,
                user_id=user.id,
            )
            raise ScheduledEndOutOfRangeError()

        end += datetime.timedelta(
            days=(self.days_in_transition or 0)
        )  # include transition phase
        log.debug(
            "Determined scheduled end of module %s for user %s: %s.", self, user, end
        )
        return end

    def prepare_user_for_auto_transition(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        _AUTO_TRANSITION_REGISTRY[self.phase_logic](self, user)  # type: ignore[index] # Invalid index type "str" for "Dict[PhaseLogic, Callable[[Any, Any], Any]]"; expected type "PhaseLogic"

    # TODO: [Tracks] Move instances once we move to new Tracks ORM
    @classmethod
    def id_by_name(cls, module_name: str) -> int:  # type: ignore[return] # Missing return statement
        try:
            return cls._name_to_id()[module_name]
        except KeyError:
            log.error("No configured module found.", module_name=module_name)

    # TODO: [Tracks] Move instances once we move to new Tracks ORM
    @classmethod
    def name_by_id(cls, id: int) -> str:  # type: ignore[return] # Missing return statement
        name_id = cls._name_to_id()
        try:
            return {name for name, id_ in name_id.items() if id_ == id}.pop()
        except KeyError:
            log.error("No configured module found.", module_id=id)

    @classmethod
    @functools.lru_cache(maxsize=1)
    def _name_to_id(cls) -> dict:
        return {
            module.name: module.id
            for module in cls.query.with_entities(cls.id, cls.name).all()
        }


class Phase(TimeLoggedModelBase):
    __tablename__ = "phase"

    id = Column(Integer, primary_key=True)
    module_id = Column(Integer, ForeignKey("module.id"), nullable=False)
    module = relationship(
        "Module",
        backref="phases",
        foreign_keys=[module_id],
        doc="The module in which this phase is defined.",
    )
    name = Column(
        String(140),
        nullable=False,
        unique=False,
        doc="The logical name of the phase.\n\n"
        "For weekly phases use the form week-[number] (e.g. week-20).\n"
        "For entry phases in static modules use the module name (e.g. generic).",
    )
    frontend_name = Column(
        String(140),
        nullable=True,
        unique=False,
        doc="The user-facing name of the phase (e.g. Week 20, Month 3).",
    )
    is_entry = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Users may join module at this phase.",
    )
    is_transitional = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Users are moved to this phase at the end of their program.",
    )
    onboarding_assessment_lifecycle_id = Column(
        Integer, ForeignKey("assessment_lifecycle.id")
    )
    onboarding_assessment_lifecycle = relationship(
        "AssessmentLifecycle",
        backref="phases",
        doc="The assessment to be taken when joining this phase from the enterprise signup flow. "
        "Module transition assessments are configured elsewhere.",
    )
    auto_transition_module_id = Column(Integer, ForeignKey("module.id"), nullable=True)
    auto_transition_module = relationship(
        "Module",
        foreign_keys=[auto_transition_module_id],
        doc="Users will be transitioned to the specified module when their care program is updated to this phase. "
        "Please take care to define an auto transition after the last phase of content you wish users to see.",
    )
    json = Column(JSONAlchemy(Text), default={})
    display_name = column_property(
        case([(frontend_name != None, frontend_name)], else_=name)
    )
    care_program_phase = relationship(
        "CareProgramPhase", uselist=False, back_populates="phase"
    )

    @classmethod
    def by_name(cls, module_name, phase_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            cls.query.join(cls.module)
            .filter(Module.name == module_name, Phase.name == phase_name)
            .options(contains_eager(cls.module))
            .one()
        )

    def __repr__(self) -> str:
        return f"<Phase[{self.id}] {self.module_name}/{self.name}>"

    __str__ = __repr__

    @property
    def intro_appointment_purpose(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.module.name == "pregnancy":
            return "birth_needs_assessment"
        elif self.module.name == "postpartum":
            return "introduction"
        return f"introduction_{self.module.name}"

    @validates("auto_transition_module")
    def validate_auto_transition_module(self, _key, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        assert (
            value is None
            or value.phase_logic not in _AUTO_TRANSITION_NOT_IMPLEMENTED_REGISTRY
        ), "Auto transition behavior has not yet been defined for the selected module."
        return value

    @hybrid_property
    def module_name(self) -> str:
        return self.module.name

    @module_name.expression  # type: ignore[no-redef] # Name "module_name" already defined on line 678
    def module_name(cls) -> Union[Column, str]:
        return Module.name

    @hybrid_property
    def module_display_name(self) -> str:
        return self.module.display_name

    @module_display_name.expression  # type: ignore[no-redef] # Name "module_display_name" already defined on line 686
    def module_display_name(cls):
        return Module.display_name


def validate_transitional_phase(mapper, connect, target):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Ensure one or none transitional phase per module."""
    if len([p for p in target.module.phases if p.is_transitional]) > 1:
        raise ValueError(
            f"There could only be one or none transitional phase per module. object={target}"
        )


event.listen(Phase, "before_update", validate_transitional_phase)
event.listen(Phase, "before_insert", validate_transitional_phase)


class CareProgramPhase(TimeLoggedModelBase):
    __tablename__ = "care_program_phase"

    id = Column(Integer, primary_key=True)

    program_id = Column(Integer, ForeignKey("care_program.id"), nullable=False)
    program = relationship("CareProgram", backref="phase_history")

    phase_id = Column(Integer, ForeignKey("phase.id"), unique=True, nullable=True)
    phase = relationship(Phase)

    as_auto_transition = Column(Boolean, default=False, nullable=False)
    started_at = Column(DateTime(), nullable=True)
    ended_at = Column(DateTime(), nullable=True)

    def __repr__(self) -> str:
        return f"<CareProgramPhase[{self.id}] phase_id={self.phase_id}>"

    __str__ = __repr__

    @hybrid_property
    def user(self) -> "User":
        return self.program.user

    @user.expression  # type: ignore[no-redef] # Name "user" already defined on line 727
    def user(cls) -> select:
        return CareProgram.user

    @hybrid_property
    def user_id(self) -> int:
        return self.program.user_id

    @user_id.expression  # type: ignore[no-redef] # Name "user_id" already defined on line 735
    def user_id(cls) -> select:
        return CareProgram.user_id

    @classmethod
    def prior_cpp_query(cls, program_id: int, started_at: datetime.datetime) -> Query:
        query = bakery(
            lambda session: session.query(CareProgramPhase)
            .filter(
                CareProgramPhase.program_id == bindparam("program_id"),
                CareProgramPhase.started_at.isnot(None),
                CareProgramPhase.started_at < bindparam("started_at"),
            )
            .order_by(CareProgramPhase.started_at.desc())
            .limit(1)
        )
        return query(db.session()).params(program_id=program_id, started_at=started_at)

    @hybrid_property
    def phase_name(self) -> Optional[str]:
        return self.phase_id and self.phase.name

    @phase_name.expression  # type: ignore[no-redef] # Name "phase_name" already defined on line 757
    def phase_name(self):
        return Phase.name

    @hybrid_property
    def module(self) -> Optional[Module]:
        return self.phase_id and self.phase.module

    @module.expression  # type: ignore[no-redef] # Name "module" already defined on line 765
    def module(cls):
        return Phase.module

    @hybrid_property
    def module_name(self) -> Optional[str]:
        return self.phase_id and self.phase.module.name

    @module_name.expression  # type: ignore[no-redef] # Name "module_name" already defined on line 773
    def module_name(cls):
        return Phase.module_name

    @hybrid_property
    def module_display_name(self) -> Optional[str]:
        return self.phase_id and self.phase.module_display_name

    @module_display_name.expression  # type: ignore[no-redef] # Name "module_display_name" already defined on line 781
    def module_display_name(cls):
        return Phase.module_display_name


class CareProgram(TimeLoggedModelBase):
    __tablename__ = "care_program"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    user = relationship("User", backref="care_programs")

    is_employee = Column(
        Boolean,
        nullable=True,
        doc=(
            "Whether the user for this care program is employed by the associated "
            "organization or are receiving benefits through an employee of that "
            "organization."
        ),
    )

    enrollment_id = Column(Integer, ForeignKey("enrollment.id"), nullable=False)
    enrollment = relationship("Enrollment", backref="care_programs")

    target_module_id = Column(Integer, ForeignKey("module.id"))
    target_module = relationship(
        "Module", doc="The module to which this care program is transitioning."
    )

    organization_module_extension_id = Column(
        BigInteger, ForeignKey(OrganizationModuleExtension.id)
    )
    granted_extension = relationship(
        OrganizationModuleExtension,
        doc="The extension granted to this program when it was initiated.",
    )

    ignore_transitions = Column(Boolean, default=False, nullable=False)
    scheduled_end = Column(Date(), nullable=True)
    ended_at = Column(DateTime(), nullable=True)
    json = Column(JSONAlchemy(Text), default={})
    # Computed properties
    is_active = column_property(case([(ended_at == None, True)], else_=False))
    is_active_transition = column_property(
        case([((ended_at == None) & (target_module_id != None), True)], else_=False)
    )
    # Nested queries for point-in-time relationships
    # This allows us to define loading strategies for these fields.
    # SEE: https://github.com/sqlalchemy/sqlalchemy/wiki/RelationshipToLatest
    first_phase = relationship(
        CareProgramPhase,
        primaryjoin=(lambda: CareProgram.first_phase_join_expression()),
        uselist=False,
    )
    last_phase = relationship(
        CareProgramPhase,
        primaryjoin=(lambda: CareProgram.last_phase_join_expression()),
        uselist=False,
    )
    current_phase = relationship(
        CareProgramPhase,
        primaryjoin=(lambda: CareProgram.current_phase_join_expression()),
        uselist=False,
    )

    def __repr__(self) -> str:
        return (
            f"<CareProgram[{self.id}] "
            f"user_id={self.user_id} "
            f"scheduled_end={self.scheduled_end} "
            f"ended={self.ended_at}>"
        )

    __str__ = __repr__

    @classmethod
    def first_phase_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            select([CareProgramPhase.id])
            .where(CareProgramPhase.program_id == CareProgram.id)
            .order_by(CareProgramPhase.started_at.asc())
            .limit(1)
            .correlate(CareProgram)  # type: ignore[arg-type] # Argument 1 to "correlate" of "Select" has incompatible type "Type[CareProgram]"; expected "FromClause"
            .as_scalar()
        )

    @classmethod
    def first_phase_join_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (CareProgramPhase.program_id == cls.id) & (
            CareProgramPhase.id == cls.first_phase_expression()
        )

    @classmethod
    def last_phase_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            select([CareProgramPhase.id])
            .where(
                (CareProgramPhase.program_id == CareProgram.id)
                & (CareProgramPhase.started_at != None)
            )
            .order_by(CareProgramPhase.started_at.desc())
            .limit(1)
            .correlate(CareProgram)  # type: ignore[arg-type] # Argument 1 to "correlate" of "Select" has incompatible type "Type[CareProgram]"; expected "FromClause"
            .as_scalar()
        )

    @classmethod
    def last_phase_join_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (CareProgramPhase.program_id == cls.id) & (
            CareProgramPhase.id == cls.last_phase_expression()
        )

    @classmethod
    def current_phase_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            select([CareProgramPhase.id])
            .where(
                (CareProgramPhase.program_id == CareProgram.id)
                & (CareProgramPhase.started_at != None)
                & (CareProgramPhase.ended_at == None)
            )
            .order_by(CareProgramPhase.started_at.desc())
            .limit(1)
            .correlate(CareProgram)  # type: ignore[arg-type] # Argument 1 to "correlate" of "Select" has incompatible type "Type[CareProgram]"; expected "FromClause"
            .as_scalar()
        )

    @classmethod
    def current_phase_join_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (CareProgramPhase.program_id == cls.id) & (
            CareProgramPhase.id == cls.current_phase_expression()
        )

    def previous_module_phase(self) -> Optional[CareProgramPhase]:  # type: ignore[return] # Missing return statement
        """Get the final phase of the previous module in the current program."""
        if self.current_phase:
            query: baked.BakedQuery = bakery(
                lambda session: (
                    session.query(CareProgramPhase)
                    .join(Phase, CareProgramPhase.phase_id == Phase.id)
                    .filter(
                        (CareProgramPhase.program_id == bindparam("program_id"))
                        & (CareProgramPhase.started_at != None)
                        & (CareProgramPhase.ended_at != None)
                        & (Phase.module.has(Module.id != bindparam("module_id")))
                    )
                    .order_by(CareProgramPhase.ended_at.desc())
                    .limit(1)
                )
            )
            phase = (
                query(db.session())
                .params(
                    program_id=self.id, module_id=self.current_phase.phase.module_id
                )
                .one_or_none()
            )
            return phase

    @property
    def type(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # todo refactor this based on self.current_module?
        return "enterprise-maternity"

    @property
    def started_at(self) -> datetime.datetime:
        if self.first_phase:
            return self.first_phase.started_at  # type: ignore[return-value] # Incompatible return value type (got "Optional[datetime]", expected "datetime")
        else:
            return self.created_at

    @property
    def current_phase_name(self) -> Optional[str]:
        cpp = self.current_phase
        return cpp and cpp.phase_name

    @property
    def current_module(self) -> Optional[Module]:
        return self.current_phase and self.current_phase.module

    @property
    def current_module_name(self) -> Optional[str]:
        cm = self.current_module
        return cm and cm.name

    @property
    def my_program_display_name(self) -> Optional[str]:
        cm = self.current_module
        return cm and cm.display_name

    @property
    def current_partner_module(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        cm = self.current_module
        return cm and cm.partner_module

    @classmethod
    def retain_data_for_user(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return db.session.query(exists().where(cls.user_id == user.id)).scalar()

    def transition_to_phase(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, phase, across_module_boundary=False, as_auto_transition=False
    ):
        """transition_to_phase extends the phase history of this program to include phase.

        Args:
            phase: The intended new phase for program to be in.
            across_module_boundary: Boolean indicating whether or not moving from the current phase to the new phase
                                    should cross from one module to another, or None when no current phase is expected.
            as_auto_transition: Boolean indicating whether this transition satisfies an auto module transition.
        """

        if not phase:
            log.warning("No phase provided!")
            return

        if as_auto_transition:
            assert (
                across_module_boundary
            ), "Auto module transitions should only be performed across module boundaries."

        if across_module_boundary is None:
            boundary_msg = ""
        elif across_module_boundary:
            boundary_msg = " across module boundaries"
        else:
            boundary_msg = " within the same module"

        log.info("Transitioning program %s to phase %s%s.", self, phase, boundary_msg)

        current_cpp = self.current_phase
        current_p = current_cpp and current_cpp.phase
        if current_p:
            if current_p == phase:
                log.debug(
                    f"No transition needed for program {self}, already at phase {current_p}."
                )
                return

            if across_module_boundary == (current_p.module == phase.module):
                msg = "Cannot transition program {} from {} to {} where transition {} was expected."
                raise InvalidPhaseTransitionError(
                    msg.format(self, current_p, phase, boundary_msg)
                )

            current_cpp.ended_at = datetime.datetime.utcnow()
            log.info(f"Ended current program phase {current_cpp}.")

        new_phase = CareProgramPhase(
            program=self,
            phase=phase,
            as_auto_transition=as_auto_transition,
            started_at=datetime.datetime.utcnow(),
        )
        db.session.add(new_phase)
        log.info(f"Started new program phase {new_phase}.")
        return new_phase

    def was_auto_transitioned(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        cpp = self._module_boundary(self.current_module_name, first_or_last=True)
        return cpp and cpp.as_auto_transition

    def module_started_at(self, module_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        cpp = self._module_boundary(module_name, first_or_last=True)
        return cpp and cpp.started_at

    def module_ended_at(self, module_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        cpp = self._module_boundary(module_name, first_or_last=False)
        return cpp and cpp.ended_at

    def _module_boundary(self, module_name, first_or_last):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        order_direction = "asc" if first_or_last else "desc"
        return (
            db.session.query(CareProgramPhase)
            .join(Phase)
            .join(Phase.module)
            .filter(CareProgramPhase.program_id == self.id, Module.name == module_name)
            .order_by(getattr(CareProgramPhase.started_at, order_direction)())
            .first()
        )

    def terminate(self, ended_at=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not self.ended_at:
            now = datetime.datetime.utcnow()
            end_time = ended_at or now

            # set program end time
            self.ended_at = end_time
            db.session.add(self)

            # set current phase end time if applicable
            current_phase = self.current_phase
            if current_phase:
                current_phase.ended_at = end_time
                db.session.add(current_phase)

            # expiring all enterprise credits
            if not self.user.active_tracks:
                for c in self.user.credits:
                    c.expires_at = now
                db.session.add_all(self.user.credits)


class Enrollment(TimeLoggedModelBase):
    __tablename__ = "enrollment"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    organization = relationship("Organization", backref="enrollments")

    def __repr__(self) -> str:
        return f"<Enrollment[{self.id}] organization_id={self.organization_id}>"

    __str__ = __repr__
