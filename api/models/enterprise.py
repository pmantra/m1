import datetime
import enum
import os
import secrets
import string
import uuid
from typing import TYPE_CHECKING, Any, Collection, Iterable, Optional, Sequence, Tuple
from warnings import warn

from dateutil.parser import parse
from flask_babel import force_locale
from google.cloud import storage
from pymysql import Connection
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    FetchedValue,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    case,
    event,
    func,
    inspect,
    select,
    tuple_,
)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapper, Query, column_property, relationship, validates

from appointments.models.payments import Credit
from common import stats
from geography.repository import CountryRepository
from models.base import (
    BoolJSONProperty,
    DateJSONProperty,
    ModelBase,
    ObjectJSONProperty,
    StringJSONProperty,
    TimeLoggedModelBase,
    TimeLoggedSnowflakeModelBase,
    db,
)
from models.marketing import CapturePageType, Resource
from models.tracks import get_track
from models.tracks.client_track import ZendeskClientTrack
from utils.cdn import signed_cdn_url
from utils.data import JSONAlchemy, normalize_phone_number
from utils.log import logger
from utils.log_model_usage import log_model_usage

if TYPE_CHECKING:
    from models.tracks.track import TrackConfig, TrackName

log = logger(__name__)
CSV_INGESTION_BUCKET = os.environ.get("CSV_INGESTION_BUCKET")
USER_ASSET_BUCKET = os.environ.get("USER_ASSET_BUCKET")
USER_ASSET_DOWNLOAD_EXPIRATION = 120  # in seconds
USER_ASSET_THUMBNAIL_EXPIRATION = 600  # in seconds
BMS_ORDER_RESOURCE = "maven-milk-breast-milk-shipping-and-travel-kits"

TRUTHY = frozenset((True, "true", 1, "1", "y", "yes"))

DEFAULT_ORG_FIELD_MAP = {
    "date_of_birth": "date_of_birth",
    "email": "work_email",
    "unique_corp_id": "employee_id",
    "employer_assigned_id": "employer_assigned_id",
    "dependent_id": "",
    "gender": "sex",
    "beneficiaries_enabled": "",
    "wallet_enabled": "wallet_enabled",
    "office_id": "",
    "work_state": "work_state",
    "employee_first_name": "first_name",
    "employee_last_name": "last_name",
    "dependent_relationship_code": "",
    "lob": "",
    "salary_tier": "",
    "plan_carrier": "insurance_carrier",
    "plan_name": "insurance_plan",
    "cobra_coverage": "",
    "company_couple": "",
    "address_1": "address_1",
    "address_2": "address_2",
    "city": "city",
    "state": "state",
    "zip_code": "zip_code",
    "country": "work_country",
    "employee_status_code": "",
    "subcompany_code": "",
    "union_status": "",
    "employee_start_date": "employee_start_date",
    "wallet_eligibility_start_date": "employee_wallet_eligibility_date",
}

# TODO : If we want to extend out the fields we allow for use in generating our composite-key for the externalID used for an org, they should be added here. Right now, we are only using 'clientID' to generate our externalID
EXTERNAL_IDENTIFIER_FIELD_MAP = {
    "client_id": "client_id",
    "customer_id": "customer_id",
}

HEALTH_PLAN_FIELD_MAP = {
    "maternity_indicator_date": "maternity_indicator_date",
    "maternity_indicator": "",
    "delivery_indicator_date": "delivery_indicator_date",
    "delivery_indicator": "",
    "fertility_indicator_date": "fertility_indicator_date",
    "fertility_indicator": "",
    "p_and_p_indicator": "p_and_p_indicator",
    "client_name": "client_name",
}

USER_FLAG_INFO_TYPE_OBESITY_CALC = "obesity_calc"
USER_FLAG_INFO_TYPE_MULTI_SELECTION = "multi-selection"

organization_managers = db.Table(
    "organization_managers",
    Column("user_id", Integer, ForeignKey("user.id")),
    Column("organization_id", Integer, ForeignKey("organization.id")),
    UniqueConstraint("user_id", "organization_id"),
)

organization_approved_modules = db.Table(
    "organization_approved_modules",
    Column("module_id", Integer, ForeignKey("module.id")),
    Column("organization_id", Integer, ForeignKey("organization.id")),
    UniqueConstraint("module_id", "organization_id"),
)

# TODO: [Tracks] Phase 3 - delete this after verifying User.organization_role join with MemberTrack
care_program = db.Table(
    "care_program",
    Column("user_id", Integer, ForeignKey("user.id")),
    Column("organization_employee_id", Integer, ForeignKey("organization_employee.id")),
)


class ModuleExtensionLogic(enum.Enum):
    ALL = "ALL"
    NON_US = "NON_US"


def _is_all(_module, _user, _employee):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return True


def _is_non_us(_module, _user, employee):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    country_code = employee.country_code
    if country_code is None:
        log.warning(
            "Cannot determine extension for employee without country.",
            organization_employee_id=employee.id,
        )
        return None
    return country_code != "US"


class OrganizationModuleExtension(TimeLoggedSnowflakeModelBase):
    __tablename__ = "organization_module_extension"

    organization_id = Column(
        Integer,
        ForeignKey("organization.id"),
        nullable=False,
        doc="The organization for which this extension will be considered.",
    )
    module_id = Column(
        Integer,
        ForeignKey("module.id"),
        nullable=False,
        doc="The module for which this extension will be considered. "
        "When configuring an extension for a program composed of multiple modules such as maternity, "
        "please create an extension for each module a user may enroll in.",
    )
    extension_logic = Column(
        Enum(ModuleExtensionLogic, native_enum=False),
        nullable=False,
        doc="The logic used to decide if this extension should be granted.",
    )
    extension_days = Column(
        Integer,
        nullable=False,
        doc="The number of days by which a program will be extended.",
    )
    priority = Column(
        Integer,
        nullable=False,
        doc="The order in which extensions should be applied, low priorities before high priorities.",
    )
    effective_from = Column(
        Date,
        nullable=False,
        doc="The initial (inclusive) date from which this extension should be granted. "
        "This value will be used when retroactively granting extensions.",
    )
    effective_to = Column(
        Date,
        doc="The final (inclusive) date until which this extension should be granted. ",
    )

    organization = relationship("Organization")
    module = relationship("Module")

    def __repr__(self) -> str:
        return f"{self.extension_logic} {self.extension_days} days"

    __str__ = __repr__

    @property
    def admin_extension_configured(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        duplicate_priorities = db.session.query(
            OrganizationModuleExtension.query.filter(
                OrganizationModuleExtension.id != self.id,
                OrganizationModuleExtension.organization_id == self.organization_id,
                OrganizationModuleExtension.module_id == self.module_id,
                OrganizationModuleExtension.priority == self.priority,
            ).exists()
        ).scalar()
        if not duplicate_priorities:
            return "\u2713"
        return f"\u2717 {self.organization.name}/{self.module.name} extensions must have distinct priorities"


class OrganizationEmployee(TimeLoggedModelBase):
    __tablename__ = "organization_employee"

    constraints = (
        UniqueConstraint(
            "organization_id", "unique_corp_id", "dependent_id", name="org_unique_id"
        ),
        UniqueConstraint("alegeus_id", name="alegeus_id"),
    )

    id = Column(Integer, primary_key=True)

    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    organization = relationship("Organization", backref="employees")

    alegeus_id = Column(String(30))

    email = Column(String(120))
    date_of_birth = Column(Date, nullable=False)
    first_name = Column(String(40))
    last_name = Column(String(40))
    work_state = Column(String(32))

    user_organization_employees = relationship(
        "UserOrganizationEmployee",
        back_populates="organization_employee",
        cascade="all, delete-orphan",
    )

    unique_corp_id = Column(String(120), nullable=True)
    dependent_id = Column(String(120), nullable=False, default="")

    retention_start_date = Column(Date, nullable=True)

    eligibility_member_id = Column(Integer, nullable=True)

    deleted_at = Column(DateTime)

    eligibility_member_2_id = Column(Integer, nullable=True)

    eligibility_member_2_version = Column(Integer, nullable=True)

    # JSON fields....
    can_get_pregnant = BoolJSONProperty("can_get_pregnant")
    beneficiaries_enabled = BoolJSONProperty("beneficiaries_enabled", nullable=False)
    wallet_enabled = BoolJSONProperty("wallet_enabled")
    spouse_account = BoolJSONProperty("spouse_account", nullable=False)
    do_not_contact = BoolJSONProperty("do_not_contact", nullable=False)
    address = ObjectJSONProperty("address")
    state = StringJSONProperty("state")

    # to record what credits we add and when for the user
    json = Column(JSONAlchemy(Text(1000)), default=dict)

    def __repr__(self) -> str:
        return f"<OrganizationEmployee: {self.id}>"

    __str__ = __repr__

    @classmethod
    def existing_emails_query(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls, org_id: int, emails: Sequence[str], *columns
    ) -> Query:
        """Compile a query that looks for existing employees by email

        Args:
            org_id: The ID of the organization these belong to.
            emails: A sequence of emails.
            *columns: Optionally select specific columns to return

        SELECT * from organization_employee
        WHERE (organization_id, email)
        IN ((1, "foo"), ...)
        """
        warn(
            "#engineering This method is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        columns = columns or (cls,)
        q: Query = db.session.query(*columns)
        tup = tuple_(OrganizationEmployee.organization_id, OrganizationEmployee.email)
        if len(emails) == 1:
            return q.filter(tup == (org_id, emails[0]))
        return q.filter(tup.in_(((org_id, e) for e in emails)))

    @classmethod
    def existing_corp_id_query(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls, org_id: int, keys: Sequence[Tuple[str, str]], *columns
    ) -> Query:
        """Compile a query that looks for existing employees by their unique id pair.

        Args:
            org_id: The ID of the organization these belong to.
            keys: A sequence of (unique_corp_id, dependent_id) pairs.
            *columns: Optionally select specific columns to return

        SELECT * from organization_employee
        WHERE (organization_id, unique_corp_id, dependent_id)
        IN ((1, "foo", "bar"), ...)
        """
        warn(
            "#engineering This method is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        columns = columns or (cls,)
        q: Query = db.session.query(*columns)
        tup = tuple_(
            OrganizationEmployee.organization_id,
            OrganizationEmployee.unique_corp_id,
            OrganizationEmployee.dependent_id,
        )
        if len(keys) == 1:
            return q.filter(tup == (org_id, *keys[0]))
        return q.filter(tup.in_(((org_id, *ks) for ks in keys)))

    @property
    def country_code(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        warn(
            "#engineering This method is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        _c = (self.json or {}).get("address", {}).get("country")
        if country := CountryRepository().get_by_name(name=_c):
            return country.alpha_2

    @property
    def country(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        warn(
            "#engineering This method is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        return CountryRepository().get(country_code=self.country_code)

    @property
    def single_user(self) -> bool:
        """Whether this record should only be associated to a single user.

        If the org provides:

          a) coverage for only employees
          b) coverage through a selected medical plan, but beneficiaries are not enabled
              for this employee record.

        then the record can only be associated to a single user.
        """
        warn(
            "#engineering This method is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        return bool(
            self.organization.employee_only
            or (self.organization.medical_plan_only and not self.beneficiaries_enabled)
        )

    @property
    def maternity_disabled(self) -> bool:
        """Determine whether this employee record is enabled for maternity content.

        If `can_get_pregnant` is False and this only a single user may use this record.

        See Also:
            https://gitlab.mvnctl.net/maven/maven/-/merge_requests/2721#note_56094
        """
        warn(
            "#engineering This method is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        cannot_get_pregnant = self.can_get_pregnant is False
        return cannot_get_pregnant and self.single_user

    @property
    def allowed_modules(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        warn(
            "#engineering This method is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        if self.maternity_disabled:
            return self.organization.allowed_nonmaternity_modules
        return self.organization.allowed_modules

    @property
    def allowed_tracks(self) -> Collection["TrackConfig"]:
        """Analog of allowed_modules for Tracks instead of Modules"""
        warn(
            "#engineering This method is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        if self.maternity_disabled:
            return self.organization.allowed_nonmaternity_tracks
        return self.organization.allowed_tracks

    def claimed_at(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        warn(
            "#engineering This method is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        ts = None
        if self.json.get("claimed_at"):
            try:
                ts = datetime.datetime.strptime(
                    self.json["claimed_at"], "%Y-%m-%dT%H:%M:%S"
                )
            except ValueError as e:
                log.debug("Bad claimed_at timestamp recorded in json: %s", e)
        if not ts:
            credit = (
                db.session.query(Credit)
                .filter_by(organization_employee_id=self.id, user_id=user_id)
                .order_by(Credit.created_at.asc())
                .limit(1)
                .first()
            )
            if credit:
                return credit.created_at


# Some models excluded because they are producing too many custom events,
# and we are already tracking these for migration elsewhere
_ORGANIZATION_EMPLOYEE_EXCLUSIONS = frozenset(
    [
        "/api/authn/models/user.py",
        "/api/tasks/enterprise.py",
        "/api/models/tracks/member_track.py",
    ]
)


@event.listens_for(OrganizationEmployee, "init")
def receive_init_oe(target, args, kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log_model_usage(
        "OrganizationEmployee",
        exclude_files=_ORGANIZATION_EMPLOYEE_EXCLUSIONS,  # type: ignore[arg-type] # Argument "exclude_files" to "log_model_usage" has incompatible type "FrozenSet[str]"; expected "Optional[Set[str]]"
        pod_name=stats.PodNames.ELIGIBILITY,
    )


@event.listens_for(OrganizationEmployee, "load")
def receive_load_oe(target, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log_model_usage(
        "OrganizationEmployee",
        exclude_files=_ORGANIZATION_EMPLOYEE_EXCLUSIONS,  # type: ignore[arg-type] # Argument "exclude_files" to "log_model_usage" has incompatible type "FrozenSet[str]"; expected "Optional[Set[str]]"
        pod_name=stats.PodNames.ELIGIBILITY,
    )


class UserOrganizationEmployee(ModelBase):
    __tablename__ = "user_organization_employee"

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    user = relationship(
        "User",
        back_populates="user_organization_employees",
    )

    organization_employee_id = Column(
        ForeignKey("organization_employee.id", ondelete="CASCADE"), nullable=False
    )
    organization_employee = relationship(
        "OrganizationEmployee",
        back_populates="user_organization_employees",
    )

    ended_at = Column(DateTime(), nullable=True, default=None)

    def __repr__(self) -> str:
        return (
            f"<UserOrganizationEmployee {self.id} "
            f"[User: {self.user_id}] "
            f"[OrganizationEmployee: {self.organization_employee_id}]>"
        )

    __str__ = __repr__


@event.listens_for(UserOrganizationEmployee, "init")
def receive_init_uoe(target, args, kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log_model_usage("UserOrganizationEmployee", pod_name=stats.PodNames.ELIGIBILITY)


@event.listens_for(UserOrganizationEmployee, "load")
def receive_load_uoe(target, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log_model_usage(
        "UserOrganizationEmployee",
        pod_name=stats.PodNames.ELIGIBILITY,
    )


class OrganizationType(str, enum.Enum):
    REAL = "REAL"
    TEST = "TEST"
    DEMO_OR_VIP = "DEMO_OR_VIP"
    MAVEN_FOR_MAVEN = "MAVEN_FOR_MAVEN"

    def __str__(self) -> str:
        return self.value


class OrganizationEligibilityType(str, enum.Enum):
    STANDARD = "STANDARD"
    ALTERNATE = "ALTERNATE"
    FILELESS = "FILELESS"
    CLIENT_SPECIFIC = "CLIENT_SPECIFIC"
    HEALTHPLAN = "HEALTHPLAN"
    UNKNOWN = "UNKNOWN"

    def __str__(self) -> str:
        return self.value


class MatchType(enum.IntEnum):
    """Enumerate MatchTypes that indicate whether a user has potential or existing eligibility records"""

    POTENTIAL = 0
    """We have validated based on First / Last / DOB but the match is not guaranteed. The user doesn't have an existing
    org so we cannot determine which orgs we should be searching for"""

    POTENTIAL_CURRENT_ORGANIZATION = 1
    """The user originally matched to an eligibility record in their current org, but that record doesn't have
    eligibility anymore. There is another record in their current org that has eligibility, but we cannot be 100% sure
    it’s the same person"""

    POTENTIAL_OTHER_ORGANIZATION = 2
    """The user originally matched to an eligibility record in their current org, but that record doesn't have
    eligibility anymore. There is another record in a different org that has eligibility, but we cannot be 100% sure
    it's the same person"""

    EXISTING_ELIGIBILITY = 3
    """The user's eligibility record that they used to register still has eligibility. We are 100% sure they have
    eligibility at the current time"""

    UNKNOWN_ELIGIBILITY = 4
    """We couldn't find any matching eligibility (but could be eligible via fileless or partner specific)"""

    INVALID = 5
    """Default match type used for handling errors"""


class Organization(ModelBase):
    __tablename__ = "organization"
    constraints = (UniqueConstraint("alegeus_employer_id", name="alegeus_employer_id"),)

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    display_name = Column(String(50), nullable=True)
    internal_summary = Column(Text)

    # The internal_type field gets exported to BigQuery, for use by the Data Team.
    # It should NOT be used in application code to determine product behavior,
    # but it exists on this model so that it can be configured in Admin.
    internal_type = Column(
        Enum(OrganizationType), nullable=False, default=OrganizationType.REAL
    )

    eligibility_type = Column(
        Enum(OrganizationEligibilityType, validate_strings=True),
        nullable=False,
        default=OrganizationEligibilityType.STANDARD,
    )

    # Deprecated: vertical groups are dispatched based on user's current module.vertical_groups
    vertical_group_version = Column(String(120), nullable=True)
    message_price = Column(Integer, default=4)

    activated_at = Column(
        # Timestamps are rounded to the nearest second when stored. When the current
        # second is rounded up, Organization#is_active evaluates to False until that
        # next second is actually reached. This causes race conditions in test code.
        # The solution is simply to force seconds to round down.
        DateTime,
        default=None,
        doc="When this organization was (or will be) activated.\n",
    )

    terminated_at = Column(
        # Timestamps are rounded to the nearest second when stored. When the current
        # second is rounded up, Organization#is_active evaluates to False until that
        # next second is actually reached. This causes race conditions in test code.
        # The solution is simply to force seconds to round down.
        DateTime,
        default=None,
        doc="Date an organization was terminated",
    )
    created_at = Column(
        DateTime,
        doc="Date the organization was created",
        default=lambda: datetime.datetime.utcnow().replace(microsecond=0),
    )

    modified_at = Column(
        DateTime,
        doc="Date the organization was last modified",
        default=lambda: datetime.datetime.utcnow().replace(microsecond=0),
    )

    directory_name = Column(
        String(120),
        nullable=True,
        doc="Census files for this organizations will be processed from this directory.",
    )
    icon = Column(String(2048), nullable=True)
    json = Column(JSONAlchemy(Text(1000)), default={})
    data_provider = Column(
        Integer,
        default=0,
        nullable=False,
        doc="If checked, indicates the organization may provide data for other organizations-"
        " i.e. this org can serve as the data provider for other sub-orgs and will provide"
        " mappings between external orgIDs and internal Maven organization IDs",
    )

    capture_page_type = Column(
        Enum(CapturePageType, validate_strings=True),
        nullable=False,
        default=CapturePageType.NO_FORM,
        doc="Capture page type either NON_FORM(static) or FORM(with interactive form)",
    )

    allowed_modules = relationship(
        "Module",
        backref="allowed_organizations",
        secondary=organization_approved_modules,
        order_by="Module.onboarding_display_order",
    )
    client_tracks = relationship(
        "ClientTrack", back_populates="organization", cascade="all, delete-orphan"
    )

    use_custom_rate = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="If true, reimbursement requests will utilize "
        "organization specific rates (custom rates) from "
        "the reimbursement_request_exchange_rates table",
    )

    medical_plan_only = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="If checked, multiple registrations are allowed for an org "
        "employee only when that org employee has beneficiaries enabled",
    )
    employee_only = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="If checked, only one registration allowed per org employee "
        "record and that registration must correlate with the allowed "
        "non-maternity modules based on the 'can_get_pregnant' status "
        "of the org employee",
    )
    _bms_enabled = Column("bms_enabled", Boolean, default=False, nullable=False)
    rx_enabled = Column(Boolean, default=True, nullable=False)
    US_restricted = Column(Boolean, default=False, nullable=False)
    gift_card_allowed = Column(Boolean, nullable=True)
    welcome_box_allowed = Column(Boolean, default=False, nullable=False)

    education_only = Column(Boolean, default=False, nullable=False)
    alegeus_employer_id = Column(String(12), unique=True)
    _session_ttl = Column(
        "session_ttl",
        Integer,
        nullable=True,
        doc="Number of minutes of inactivity before logging a user out",
    )

    org_folder_link = StringJSONProperty("org_folder_link")
    org_script_link = StringJSONProperty("org_script_link")

    disassociate_users = BoolJSONProperty("disassociate_users", nullable=False)
    alternate_verification = BoolJSONProperty("alternate_verification", nullable=False)
    test_group_override = StringJSONProperty("test_group_override")
    employee_count = column_property(
        select([func.count(OrganizationEmployee.id)])
        .where(OrganizationEmployee.organization_id == id)
        .correlate_except(OrganizationEmployee),  # type: ignore[arg-type] # Argument 1 to "correlate_except" of "Select" has incompatible type "Type[OrganizationEmployee]"; expected "FromClause"
        deferred=True,
    )

    eligibility_fields = relationship(
        "OrganizationEligibilityField", back_populates="organization"
    )
    _deprecated_multitrack_enabled = Column(
        "multitrack_enabled", Boolean, nullable=False, default=False
    )
    benefits_url = Column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<Organization[{self.id}] {self.name}>"

    __str__ = __repr__

    marketing_name = column_property(
        case(
            [(display_name.isnot(None), display_name)],
            else_=func.replace(name, "_", " "),
        )
    )

    def create_alegeus_employer_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.internal_type not in [
            OrganizationType.TEST,
            OrganizationType.DEMO_OR_VIP,
        ]:
            self.alegeus_employer_id = "MVN" + secrets.token_hex(4)
            db.session.commit()

    @hybrid_property
    def bms_enabled(self):
        return self._bms_enabled

    @bms_enabled.setter  # type: ignore[no-redef] # Name "bms_enabled" already defined on line 815
    def bms_enabled(self, val):
        resource = (
            db.session.query(Resource)
            .filter(Resource.slug == BMS_ORDER_RESOURCE)
            .first()
        )
        if val is True:
            if resource and resource not in self.allowed_resources:
                self.allowed_resources.append(resource)
                log.info("BMS Enabled resource added")
            elif not resource:
                raise Exception(
                    "BMS Enabled resource not available. Add Resource for BMS Order Form."
                )
        else:
            if resource and resource in self.allowed_resources:
                self.allowed_resources.remove(resource)
                log.info("BMS Enabled resource removed")
        self._bms_enabled = val

    @hybrid_property
    def session_ttl(self):
        return self._session_ttl or (60 * 24 * 7)  # default value of 7 days

    @session_ttl.setter  # type: ignore[no-redef] # Name "session_ttl" already defined on line 840
    def session_ttl(self, val):
        self._session_ttl = val

    @property
    def is_active(self) -> bool:
        return (
            self.activated_at is not None
            and self.activated_at <= datetime.datetime.utcnow()
        ) and (
            self.terminated_at is None
            or self.terminated_at >= datetime.datetime.utcnow()
        )

    @is_active.setter
    def is_active(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.activated_at = datetime.datetime.utcnow() if val else None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[datetime]", variable has type "datetime")

    @property
    def field_map(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        custom = (self.json or {}).get("field_map", {})
        field_map = {**DEFAULT_ORG_FIELD_MAP, **custom}
        return field_map

    @field_map.setter
    def field_map(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.json is None:
            self.json = {}

        if not isinstance(val, dict):
            log.debug("Cannot set field_map - not a dict!")
            return

        for key in val.keys():
            if key not in DEFAULT_ORG_FIELD_MAP:
                raise ValueError(f"Invalid key for field map: {key}")

        self.json["field_map"] = val

    @property
    def custom_attributes_field_map(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        custom_attributes_field_map = (self.json or {}).get(
            "custom_attributes_field_map", {}
        )
        return custom_attributes_field_map

    @custom_attributes_field_map.setter
    def custom_attributes_field_map(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.json is None:
            self.json = {}

        if not isinstance(val, dict):
            log.debug("Cannot set custom_attribute_field_map - not a dict!")
            return

        self.json["custom_attributes_field_map"] = val

    @property
    def optional_field_map_affiliations(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        custom = (self.json or {}).get("optional_field_map_affiliations", {})
        field_map = {**EXTERNAL_IDENTIFIER_FIELD_MAP, **custom}
        return field_map

    @optional_field_map_affiliations.setter
    def optional_field_map_affiliations(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.json is None:
            self.json = {}

        if not isinstance(val, dict):
            log.debug("Cannot set field_map - not a dict!")
            return

        for key in val.keys():
            if key not in EXTERNAL_IDENTIFIER_FIELD_MAP:
                raise ValueError(f"Invalid key for field map: {key}")

        self.json["optional_field_map_affiliations"] = val

    @property
    def health_plan_field_map_affiliations(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        custom = (self.json or {}).get("health_plan_field_map_affiliations", {})
        field_map = {**HEALTH_PLAN_FIELD_MAP, **custom}
        return field_map

    @health_plan_field_map_affiliations.setter
    def health_plan_field_map_affiliations(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.json is None:
            self.json = {}

        if not isinstance(val, dict):
            log.debug("Cannot set field_map - not a dict!")
            return

        for key in val.keys():
            if key not in HEALTH_PLAN_FIELD_MAP:
                raise ValueError(f"Invalid key for field map: {key}")

        self.json["health_plan_field_map_affiliations"] = val

    @property
    def org_employee_primary_key(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (self.json or {}).get("PK_COLUMN", "unique_corp_id").lower()

    @org_employee_primary_key.setter
    def org_employee_primary_key(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.json is None:
            self.json = {}

        if val in ("email", "unique_corp_id"):
            self.json["PK_COLUMN"] = val

    @property
    def allowed_nonmaternity_modules(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return [m for m in self.allowed_modules if not m.is_maternity]

    @property
    def allowed_nonmaternity_tracks(self) -> Collection["TrackConfig"]:
        return [t for t in self.allowed_tracks if not t.is_maternity]

    @property
    def allowed_tracks(self) -> Collection["TrackConfig"]:
        return [
            get_track(ct.track)
            for ct in self.client_tracks
            if ct.is_available_to_members
        ]

    def client_track(self, track: "TrackName"):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return next((ct for ct in self.client_tracks if ct.track == track), None)

    @property
    def org_employee_metadata(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        data = {}

        if self.json.get("retention_start_date"):
            data["retention_start_date"] = parse(
                self.json.get("retention_start_date")
            ).date()

        return data

    @property
    def multitrack_enabled(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        from models.tracks import TrackName

        # Currently, for a user to have two tracks, one of them must be the
        # parenting & pediatrics track, so "multitrack" == organization has P&P.
        return TrackName.PARENTING_AND_PEDIATRICS in [
            t.name for t in self.allowed_tracks
        ]

    @validates("education_only")
    def validate_education_only(self, _key, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value and self.rx_enabled:
            raise ValueError(
                "cannot set education only to true when rx_enabled is also true"
            )

        return value


@event.listens_for(Organization, "after_insert")
def create_zendesk_org_on_org_creation(
    mapper: Mapper, connection: Connection, target: Organization
) -> None:
    from messaging.services.zendesk import update_zendesk_org

    org_name = target.display_name if target.display_name else target.name
    with force_locale("en"):
        update_zendesk_org.delay(
            target.id,
            org_name,
            [
                ZendeskClientTrack.build_from_client_track(track)
                for track in target.client_tracks
            ],
            target.US_restricted,
        )


@event.listens_for(Organization, "after_update")
def update_zendesk_org_on_org_update(
    mapper: Mapper, connection: Connection, target: Organization
) -> None:
    from messaging.services.zendesk import update_zendesk_org

    name_history = inspect(target).get_history("name", True)
    id_history = inspect(target).get_history("id", True)
    offshore_restriction_history = inspect(target).get_history("US_restricted", True)
    if (
        name_history.has_changes()
        or id_history.has_changes()
        or offshore_restriction_history.has_changes()
    ):
        org_name = target.display_name if target.display_name else target.name
        with force_locale("en"):
            update_zendesk_org.delay(
                target.id,
                org_name,
                [
                    ZendeskClientTrack.build_from_client_track(track)
                    for track in target.client_tracks
                ],
                target.US_restricted,
            )


class ExternalIDPNames(str, enum.Enum):
    VIRGIN_PULSE = "VIRGIN_PULSE"
    OKTA = "OKTA"
    CASTLIGHT = "CASTLIGHT"
    OPTUM = "OPTUM"

    def __str__(self) -> str:
        return self.value


class OrganizationExternalID(ModelBase):
    """
    Used to store unique IDs for the clients of our SSO providers so that we can map
    SSO clients to our internal clients.
    """

    __tablename__ = "organization_external_id"
    constraints = (
        UniqueConstraint("data_provider_organization_id", "external_id"),
        UniqueConstraint("identity_provider_id", "external_id"),
    )

    id = Column(Integer, primary_key=True)
    idp = Column(
        Enum(ExternalIDPNames),
        nullable=True,
        doc="DEPRECATED: The name of the identity provider.",
    )
    identity_provider_id = Column(
        Integer, server_default=FetchedValue(), server_onupdate=FetchedValue()
    )
    external_id = Column(
        String(120),
        nullable=False,
        doc="The unique identifier for an organization set by the IdP.",
    )

    organization_id = Column(Integer, ForeignKey(Organization.id), nullable=False)
    data_provider_organization_id = Column(
        ForeignKey(Organization.id),
        nullable=True,
    )

    organization = relationship(
        "Organization", backref="external_ids", foreign_keys=[organization_id]
    )

    data_provider_organization = relationship(
        "Organization",
        primaryjoin=lambda: OrganizationExternalID.get_data_provider_organizations(),
    )

    @classmethod
    def get_data_provider_organizations(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (cls.data_provider_organization_id == Organization.id) & (
            Organization.data_provider == 1
        )


class OrganizationRewardsExport(TimeLoggedModelBase):
    """
    Used to store record of reward event exports to third parties
    """

    __tablename__ = "organization_rewards_export"

    id = Column(Integer, primary_key=True)
    organization_external_id_id = Column(ForeignKey("organization_external_id.id"))
    organization_external_id = relationship(
        "OrganizationExternalID", backref="reward_exports"
    )


class EmailEligibilityLogic(str, enum.Enum):
    CLIENT_SPECIFIC = "CLIENT_SPECIFIC"
    FILELESS = "FILELESS"

    def __str__(self) -> str:
        return self.value


class OrganizationEmailDomain(ModelBase):
    """Used during enterprise user onboarding to determine the logic used for an
    enterprise eligibility check.
    """

    __tablename__ = "organization_email_domain"

    id = Column(Integer, primary_key=True)
    domain = Column(
        String(120),
        unique=True,
        nullable=False,
        doc="The domain name part of an organization’s employee email addresses.",
    )
    eligibility_logic = Column(
        Enum(EmailEligibilityLogic, native_enum=False),
        nullable=False,
        default=EmailEligibilityLogic.CLIENT_SPECIFIC,
        doc="The logic used to decide eligibility for users with emails ending in "
        "this domain.",
    )

    organization_id = Column(ForeignKey("organization.id"), nullable=False)
    organization = relationship("Organization", backref="email_domains")

    @classmethod
    def for_email(cls, email: str) -> Optional["OrganizationEmailDomain"]:
        try:
            email_domain = email.split("@")[-1]
        except IndexError:
            return None

        return db.session.query(cls).filter(cls.domain == email_domain).one_or_none()


class OrganizationEligibilityField(ModelBase):
    """If an organization has an OrganizationEligibilityField row, then the set fields
    are used for doing organization specific eligibility checks, rather than the default
    standard and alternate eligibility verifications.
    """

    __tablename__ = "organization_eligibility_field"
    constraints = (UniqueConstraint("organization_id", "name"),)

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    label = Column(
        String(120), nullable=False, doc="The display label used on frontends."
    )

    organization_id = Column(ForeignKey("organization.id"), nullable=False)
    organization = relationship("Organization", back_populates="eligibility_fields")


class NeedsAssessmentTypes(enum.Enum):
    PREGNANCY = "PREGNANCY"  # notes for intro appt
    POSTPARTUM = "POSTPARTUM"  # notes for intro appt
    # onboarding NAs are filled out at signup and used to match for care team
    PREGNANCY_ONBOARDING = "PREGNANCY_ONBOARDING"
    POSTPARTUM_ONBOARDING = "POSTPARTUM_ONBOARDING"
    EGG_FREEZING_ONBOARDING = "EGG_FREEZING_ONBOARDING"
    FERTILITY_ONBOARDING = "FERTILITY_ONBOARDING"
    PREGNANCYLOSS_ONBOARDING = "PREGNANCYLOSS_ONBOARDING"
    SURROGACY_ONBOARDING = "SURROGACY_ONBOARDING"
    ADOPTION_ONBOARDING = "ADOPTION_ONBOARDING"
    BREAST_MILK_SHIPPING_ONBOARDING = "BREAST_MILK_SHIPPING_ONBOARDING"
    TRYING_TO_CONCEIVE_ONBOARDING = "TRYING_TO_CONCEIVE_ONBOARDING"
    GENERAL_WELLNESS_ONBOARDING = "GENERAL_WELLNESS_ONBOARDING"
    PARENTING_AND_PEDIATRICS_ONBOARDING = "PARENTING_AND_PEDIATRICS_ONBOARDING"
    PARTNER_FERTILITY_ONBOARDING = "PARTNER_FERTILITY_ONBOARDING"
    PARTNER_PREGNANCY_ONBOARDING = "PARTNER_PREGNANCY_ONBOARDING"
    PARTNER_NEWPARENT_ONBOARDING = "PARTNER_NEWPARENT_ONBOARDING"
    M_QUIZ = "M_QUIZ"
    E_QUIZ = "E_QUIZ"
    C_QUIZ = "C_QUIZ"
    REFERRAL_REQUEST = "REFERRAL_REQUEST"
    REFERRAL_FEEDBACK = "REFERRAL_FEEDBACK"


class AssessmentLifecycleTrack(ModelBase):
    __tablename__ = "assessment_lifecycle_tracks"
    constraints = (UniqueConstraint("track_name"),)

    assessment_lifecycle_id = Column(
        Integer, ForeignKey("assessment_lifecycle.id"), primary_key=True
    )
    assessment_lifecycle = relationship("AssessmentLifecycle")

    track_name = Column("track_name", String(120), primary_key=True)


class AssessmentLifecycle(TimeLoggedModelBase):
    __tablename__ = "assessment_lifecycle"
    constraints = (UniqueConstraint("type", "name"),)

    id = Column(Integer, primary_key=True)
    type = Column(Enum(NeedsAssessmentTypes), nullable=False)
    name = Column(String(70), nullable=False)

    allowed_tracks = relationship(
        "AssessmentLifecycleTrack", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        type_string = (
            self.type.value
            if isinstance(self.type, NeedsAssessmentTypes)
            else self.type
        )
        return f"<AssessmentLifecycle[{self.id}] type={type_string} name={self.name}>"

    __str__ = __repr__

    @property
    def latest_assessment(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            max(self.assessments, key=lambda x: x.version) if self.assessments else None
        )

    def current_assessment_for_user(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Return the latest version of the assessment if none has been started
        Otherwise return the current started assessment
        :return:
        """
        cur_asmt = None
        for assessment in self.assessments:
            needs_assessments = assessment.user_assessments
            if any(
                (not na.completed and na.user_id == user.id) for na in needs_assessments
            ):
                cur_asmt = assessment
                break
        else:
            cur_asmt = self.latest_assessment

        return cur_asmt

    @property
    def allowed_track_names(self) -> Iterable["TrackName"]:
        """
        Returns the names of the tracks for which this is the onboarding assessment lifecycle.
        """
        from models.tracks import TrackName

        return [TrackName(t.track_name) for t in self.allowed_tracks]


USER_ASSESSMENT_IDS_QUERY = """
SELECT CASE WHEN count(na.id) > 0 THEN max(na.assessment_id) ELSE max(a.id) END
FROM assessment a
    JOIN assessment_lifecycle al ON al.id = a.lifecycle_id
    LEFT JOIN needs_assessment na ON na.assessment_id = a.id
        AND na.user_id = :user_id
        AND na.completed IS TRUE
WHERE al.type IN :lifecycle_types
GROUP BY a.lifecycle_id
"""


class Assessment(TimeLoggedModelBase):
    __tablename__ = "assessment"
    constraints = (UniqueConstraint("lifecycle_id", "version"),)

    id = Column(Integer, primary_key=True)
    lifecycle_id = Column(ForeignKey("assessment_lifecycle.id"))
    version = Column(Integer, nullable=False, default=1)
    title = Column(String(70), nullable=True)
    description = Column(Text(), nullable=True)
    icon = Column(String(2048), nullable=True)
    slug = Column(String(2048), nullable=True)
    estimated_time = Column(Integer, nullable=True)  # in seconds
    image_id = Column(ForeignKey("image.id"), nullable=True)
    quiz_body = Column(JSONAlchemy(Text()), default={})
    score_band = Column(JSONAlchemy(Text()), default={})
    json = Column(JSONAlchemy(Text()), default={})

    lifecycle = relationship("AssessmentLifecycle", backref="assessments")
    image = relationship("Image")

    def __repr__(self) -> str:
        return (
            f"<Assessment[{self.id}] lifecycle={self.lifecycle} version={self.version}>"
        )

    __str__ = __repr__

    @property
    def type(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        warn(
            "#pod-care-management This class is attached to stale data.",
            DeprecationWarning,
        )
        return self.lifecycle.type if self.lifecycle else None

    @property
    def name(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        warn(
            "#pod-care-management This class is attached to stale data.",
            DeprecationWarning,
        )
        return self.lifecycle.name if self.lifecycle else None

    @classmethod
    def ids_for_user(cls, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        warn(
            "#pod-care-management This class is attached to stale data.",
            DeprecationWarning,
        )
        """
        Return the relevant assessment ids for the given user_id - If the user
        has completed a particular assessment version of an assessment
        lifecycle, that assessment id will be included, otherwise the latest
        assessment id of each assessment lifecycle is returned.
        """
        return [
            i[0]
            for i in db.session.execute(
                USER_ASSESSMENT_IDS_QUERY,
                {
                    "user_id": user_id,
                    "lifecycle_types": [
                        NeedsAssessmentTypes.E_QUIZ.value,
                        NeedsAssessmentTypes.M_QUIZ.value,
                        NeedsAssessmentTypes.C_QUIZ.value,
                    ],
                },
            )
        ]


class NeedsAssessment(TimeLoggedModelBase):
    __tablename__ = "needs_assessment"

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey("user.id"))
    appointment_id = Column(ForeignKey("appointment.id"))
    assessment_id = Column(ForeignKey("assessment.id"), nullable=True)
    completed = Column(Boolean, nullable=True)
    json = Column(JSONAlchemy(Text()), default={})

    user = relationship("User", backref="assessments")
    appointment = relationship("Appointment", backref="assessments")
    assessment_template = relationship("Assessment", backref="user_assessments")

    def __repr__(self) -> str:
        return f"<NeedsAssessment[{self.id}] Type={self.type} Appointment[{self.appointment_id}]>"

    __str__ = __repr__

    def update_completed_from_json(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.json:
            self.completed = self.json.get("meta", {}).get("completed", False)

    @property
    def status(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        warn(
            "#pod-care-management This class is attached to stale data.",
            DeprecationWarning,
        )
        _json = self.json or {}
        _answers = _json.get("answers")

        self.update_completed_from_json()
        if self.completed:
            return "completed"
        elif _answers:
            return "incomplete"
        else:
            return "not_started"

    @property
    def type(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        warn(
            "#pod-care-management This class is attached to stale data.",
            DeprecationWarning,
        )
        return self.assessment_template.type if self.assessment_template else None

    @property
    def version(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        warn(
            "#pod-care-management This class is attached to stale data.",
            DeprecationWarning,
        )
        return self.assessment_template.version if self.assessment_template else None

    @classmethod
    def retain_data_for_user(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        warn(
            "#pod-care-management This class is attached to stale data.",
            DeprecationWarning,
        )
        return db.session.query(
            cls.list_by_user_and_kind(user, is_medical=True).exists()
        ).scalar()

    @classmethod
    def list_by_user_and_kind(cls, user, is_medical):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        warn(
            "#pod-care-management This class is attached to stale data.",
            DeprecationWarning,
        )
        return (
            db.session.query(NeedsAssessment)
            .join(Assessment)
            .join(AssessmentLifecycle)
            .filter(
                NeedsAssessment.user_id == user.id,
                AssessmentLifecycle.type.in_(
                    [
                        v.value
                        for v in list(NeedsAssessmentTypes)
                        if ("QUIZ" not in v.value) == is_medical
                    ]
                ),
            )
        )

    @classmethod
    # Warning!  Some assessment lifecycles share a type but are quite different
    # (e.g. E_QUIZ).  Use only if you're sure that's not your situation.
    def get_latest_by_user_id_and_lifecycle_type(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        cls, user_id, assessment_id, lifecycle_type
    ):
        warn(
            "#pod-care-management This class is attached to stale data.",
            DeprecationWarning,
        )
        query = (
            NeedsAssessment.query.filter(NeedsAssessment.user_id == user_id)
            .join(Assessment)
            .join(AssessmentLifecycle)
            .order_by(NeedsAssessment.created_at.desc())
        )

        if assessment_id:
            query = query.filter(NeedsAssessment.assessment_id == assessment_id)

        if lifecycle_type:
            query = query.filter(AssessmentLifecycle.type == lifecycle_type)

        return query.all()


def sync_completed_status(mapper, connect, target):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    target.update_completed_from_json()


event.listen(NeedsAssessment, "before_update", sync_completed_status)
event.listen(NeedsAssessment, "before_insert", sync_completed_status)


class UserAssetState(enum.Enum):
    UPLOADING = "UPLOADING"
    REJECTED = ("REJECTED",)
    COMPLETE = "COMPLETE"
    CANCELED = "CANCELED"


"""
The database table user_asset_appointment is used with reporting on
various deliverables associated with appointments. For example, by
associating media with the product experience, medical outcomes can
be tied with whether members were exposed to certain media or practitioner
interactions.
"""
user_asset_appointment = db.Table(
    "user_asset_appointment",
    Column(
        "user_asset_id",
        BigInteger,
        ForeignKey("user_asset.id"),
        primary_key=True,
        nullable=False,
    ),
    Column("appointment_id", Integer, ForeignKey("appointment.id"), nullable=False),
)


class UserAssetMessage(ModelBase):
    __tablename__ = "user_asset_message"

    user_asset_id = Column(
        BigInteger, ForeignKey("user_asset.id"), nullable=False, primary_key=True
    )
    message_id = Column(Integer, ForeignKey("message.id"), nullable=False)
    position = Column(
        Integer,
        default=None,
        doc="A column used to maintain the order of message attachments.",
    )

    user_asset = relationship("UserAsset")
    message = relationship("Message")


class UserAsset(TimeLoggedSnowflakeModelBase):
    __tablename__ = "user_asset"

    user_id = Column(ForeignKey("user.id"))
    state = Column(
        Enum(UserAssetState),
        nullable=False,
        doc="State represents the various conditions an asset may be in.\n\n"
        "UPLOADING: The asset has been created, but its contents have not yet been delivered to the server.\n"
        "REJECTED: The asset was created and uploaded, but the upload could not be finalized.\n"
        "COMPLETE: The asset has been created, and its contents are ready to be served.\n"
        "CANCELED: The asset was created, but its contents will never be delivered to the server.",
    )
    file_name = Column(
        String(4096), nullable=False, doc="The original file name chosen by the user."
    )
    content_type = Column(
        String(255),
        nullable=False,
        doc="The mime type of this asset as parsed by libmagic, available when state is COMPLETE.",
    )
    content_length = Column(
        BigInteger,
        nullable=False,
        doc="The asset size in bytes, available when state is COMPLETE.",
    )

    user = relationship("User", backref="assets")

    appointment = relationship(
        "Appointment", backref="assets", secondary=user_asset_appointment, uselist=False
    )

    _message = relationship("UserAssetMessage", uselist=False)
    message = association_proxy(
        "_message",
        "message",
        cascade_scalar_deletes=True,
        creator=lambda m: UserAssetMessage(message=m),
    )

    _bucket = None

    @classmethod
    def bucket(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if cls._bucket is None:
            cls._bucket = cls.client().get_bucket(USER_ASSET_BUCKET)
        return cls._bucket

    @classmethod
    def client(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return storage.Client.from_service_account_json(
            "/google-svc-accounts/user-file.json"
        )

    def __repr__(self) -> str:
        return f"<UserAsset [{self.id}] User={self.user_id}>"

    __str__ = __repr__

    @property
    def external_id(self) -> str:
        return str(self.id)

    @property
    def blob_name(self) -> str:
        return f"o/{self.id}"

    @property
    def blob(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.bucket().blob(self.blob_name)

    def in_terminal_state(self) -> bool:
        return self.state != UserAssetState.UPLOADING

    def direct_download_url(self, inline: bool = False) -> str:
        ending = "?response-content-disposition=inline" if inline else ""
        return signed_cdn_url(
            f"/{self.blob_name}{ending}", USER_ASSET_DOWNLOAD_EXPIRATION
        )

    def direct_thumbnail_url(self) -> str:
        return signed_cdn_url(
            f"/t/fit-in/500x500/{self.blob_name}", USER_ASSET_THUMBNAIL_EXPIRATION
        )

    def can_be_read_by(self, user) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # as asset owner
        if self.user == user:
            return True

        # as channel direct participant
        if (
            self.message
            and self.message.channel
            and self.message.channel.is_active_participant(user)
        ):
            return True

        # as CA on wallet channel
        if (
            self.message
            and self.message.channel
            and self.message.channel.is_wallet
            and user.is_care_coordinator
        ):
            return True

        # Care Advocates work on each others' channels
        if (
            self.message
            and self.message.channel
            and self.message.channel.practitioner
            and self.message.channel.practitioner.is_care_coordinator
            and user.is_care_coordinator
        ):
            return True

        # as appointment participant
        if self.appointment:
            return user in [self.appointment.member, self.appointment.practitioner]

        # none of the above
        return False


class BusinessLead(TimeLoggedModelBase):
    __tablename__ = "business_lead"

    id = Column(Integer, primary_key=True)
    json = Column(JSONAlchemy(Text))

    def __repr__(self) -> str:
        return f"<BusinessLead[{self.id}]>"

    __str__ = __repr__


class UserProgramHistory(TimeLoggedModelBase):
    __tablename__ = "user_program_history"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("user.id"), nullable=True, unique=True)
    user = relationship("User", backref="program_history")

    json = Column(JSONAlchemy(Text))

    def __repr__(self) -> str:
        return f"<UserProgramHistory [{self.id}/{self.user_id}]>"

    __str__ = __repr__

    @property
    def phase(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (self.json or {}).get("phase")

    @phase.setter
    def phase(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.json is None:
            self.json = {}
        self.json["phase"] = val

    @property
    def module(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (self.json or {}).get("module")

    @module.setter
    def module(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.json is None:
            self.json = {}
        self.json["module"] = val


class InviteType(str, enum.Enum):
    PARTNER = "PARTNER"
    FILELESS_EMPLOYEE = "FILELESS_EMPLOYEE"
    FILELESS_DEPENDENT = "FILELESS_DEPENDENT"


class Invite(TimeLoggedModelBase):
    __tablename__ = "invite"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    type = Column(
        Enum(InviteType, native_enum=False), nullable=False, default=InviteType.PARTNER
    )

    created_by_user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    created_by_user = relationship("User", backref="invite", uselist=False)

    email = Column(String(120), nullable=False)
    name = Column(
        String(120), nullable=False, doc="The name of the recipient being invited."
    )

    json = Column(JSONAlchemy(Text), default={})

    expires_at = Column(DateTime(), nullable=True)

    date_of_birth = DateJSONProperty("date_of_birth")
    due_date = DateJSONProperty("due_date")
    last_child_birthday = DateJSONProperty("last_child_birthday")
    phone_number = StringJSONProperty(
        "phone_number"
    )  # TODO: review for international feature

    claimed = Column(Boolean, nullable=True, default=False)

    def __repr__(self) -> str:
        return f"<Invite: {self.id}>"


class PartnerInvite(TimeLoggedModelBase):
    __tablename__ = "partner_invite"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    created_by_user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    created_by_user = relationship("User", backref="partner_invite", uselist=False)

    json = Column(JSONAlchemy(Text), default={})

    claimed = Column(Boolean, nullable=True, default=False)

    def __repr__(self) -> str:
        return f"<Partner Invite: {self.id}>"


class OnboardingState(str, enum.Enum):
    USER_CREATED = "user_created"
    ERROR = "error"
    TRACK_SELECTION = "track_selection"
    ASSESSMENTS = "assessments"
    COMPLETED = "completed"

    FAILED_ELIGIBILITY = "failed_eligibility"
    FAILED_TRACK_SELECTION = "failed_track_selection"

    # Fileless Eligibility
    FILELESS_INVITED_EMPLOYEE = "fileless_invited_employee"
    FILELESS_INVITED_DEPENDENT = "fileless_invited_dependent"

    def __repr__(self) -> str:
        return self.value

    __str__ = __repr__


class UserOnboardingState(TimeLoggedModelBase):
    __tablename__ = "user_onboarding_state"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, unique=True)
    state = Column(
        Enum(OnboardingState, native_enum=False),
        nullable=False,
        default=OnboardingState.USER_CREATED,
    )

    user = relationship("User", back_populates="onboarding_state", uselist=False)

    def __repr__(self) -> str:
        return self.state

    __str__ = __repr__


class QuizAnswerBase:
    def __init__(self, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.id = kwargs.get("id")
        self.body = kwargs.get("body")

    def match(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Delegate logic to the specific answer by id
        """
        return getattr(self, f"_{self.id}")()


class QuizEvaluatorException(Exception):
    pass


class ScorableQuizAnswer(QuizAnswerBase):
    def get_question(self, needs_assessment):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.questions = (
            needs_assessment.assessment_template
            and needs_assessment.assessment_template.quiz_body.get("questions")
        )
        if not self.questions:
            raise QuizEvaluatorException(f"{needs_assessment} questions not defined!")

        try:
            question = next((q for q in self.questions if q.get("id") == self.id), None)
        except Exception as e:
            err_msg = f"{needs_assessment} questions malformed: {e}"
            log.debug(err_msg)
            raise QuizEvaluatorException(err_msg)

        if not question:
            err_msg = f"{needs_assessment} question not found: answer#{self.id}"
            log.debug(err_msg)
            raise QuizEvaluatorException(err_msg)
        return question


class EQuizAnswer(ScorableQuizAnswer):
    def tally(self, needs_assessment):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Validate and tally the correct answer.
        :param needs_assessment: the user assessment of the answer
        :return: 1 for correct answer, 0 for incorrect answer
        """
        q = self.get_question(needs_assessment)

        try:
            widget = q.get("widget", {})
            valid_answers = [o.get("value") for o in widget.get("options", {})]
        except Exception as e:
            err_msg = f"{needs_assessment} questions malformed: {e}"
            log.debug(err_msg)
            raise QuizEvaluatorException(err_msg)

        if not valid_answers:
            err_msg = f"Valid answers not found for {needs_assessment}"
            log.debug(err_msg)
            raise QuizEvaluatorException(err_msg)

        # multiple correct answers is allowed
        correct_answers = widget.get("solution", {}).get("value", [])
        if not correct_answers or not isinstance(correct_answers, list):
            err_msg = f"No correct answer defined for {needs_assessment}"
            log.debug(err_msg)
            raise QuizEvaluatorException(err_msg)

        # validate correct answers are part of all answer options
        if not set(correct_answers).issubset(set(valid_answers)):
            err_msg = f"Solution mismatching options for {needs_assessment}"
            log.debug(err_msg)
            raise QuizEvaluatorException(err_msg)

        return 1 if self.body in correct_answers else 0


class MQuizAnswer(ScorableQuizAnswer):
    def tally(self, needs_assessment):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Validate and tally the letter designation of the answer.
        :param needs_assessment: the user assessment of the answer
        :return: the upper case letter designation of the answer
        """
        question = self.get_question(needs_assessment)

        # answer body should be one of the letters
        cnt_opts = len(question.get("widget", {}).get("options", {}))
        if not cnt_opts > 0:
            err_msg = f"No options defined for {needs_assessment}"
            log.debug(err_msg)
            raise QuizEvaluatorException(err_msg)

        valid_answers = string.ascii_uppercase[:cnt_opts]
        if (
            not self.body
            or not isinstance(self.body, str)
            or len(self.body) != 1
            or self.body.upper() not in valid_answers
        ):
            err_msg = f"{needs_assessment} has an invalid answer: {self.body}"
            log.debug(err_msg)
            raise QuizEvaluatorException(err_msg)

        return self.body.upper()


class CQuizAnswer(ScorableQuizAnswer):
    def tally(self, needs_assessment):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Validate and tally the answer points.
        :param needs_assessment: the user assessment of the answer
        :return: the points of the answers
        https://gitlab.mvnctl.net/snippets/20
        """
        question = self.get_question(needs_assessment)
        try:
            options = question.get("widget", {}).get("options", [])
            valid_score_pts = [
                o.get("value") for o in options if o.get("value") is not None
            ]
            if self.body is not None and self.body not in valid_score_pts:
                err_msg = f"{needs_assessment} has an invalid answer: {self.body}"
                log.debug(err_msg)
                raise QuizEvaluatorException(err_msg)

            score_pts = int(self.body)  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
        except Exception as e:
            err_msg = f"{needs_assessment} questions malformed: {e}"
            log.debug(err_msg)
            raise QuizEvaluatorException(err_msg)

        return score_pts


org_inbound_phone_number = db.Table(
    "org_inbound_phone_number",
    Column("id", Integer, primary_key=True),
    Column("org_id", Integer, ForeignKey("organization.id"), nullable=False),
    Column(
        "inbound_phone_number_id",
        Integer,
        ForeignKey("inbound_phone_number.id"),
        nullable=False,
    ),
    UniqueConstraint("org_id"),
)


class InboundPhoneNumber(ModelBase):
    __tablename__ = "inbound_phone_number"

    id = Column(Integer, primary_key=True)
    number = Column(String(20), nullable=False, unique=True)

    organizations = relationship("Organization", secondary="org_inbound_phone_number")

    @validates("number")
    def validate_number(self, key: Any, number: str) -> str:
        if number:
            number, _ = normalize_phone_number(number, None, 20)
        return number
