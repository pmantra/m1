import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, validates

from geography import repository as geography_repository
from geography.utils import validate_country_code
from models import base
from models.tracks import TrackName


class IncentiveType(enum.Enum):
    GIFT_CARD = "Gift card"
    WELCOME_BOX = "Welcome box"


class IncentiveDesignAsset(enum.Enum):
    GENERIC_GIFT_CARD = "Generic gift card"
    AMAZON_GIFT_CARD = "Amazon gift card"
    WELCOME_BOX = "Welcome box"


class IncentiveAction(enum.Enum):
    CA_INTRO = "CA Intro"
    OFFBOARDING_ASSESSMENT = "Offboarding assessment"


class Incentive(base.TimeLoggedModelBase):
    __tablename__ = "incentive"
    id = Column(Integer, primary_key=True)
    type = Column(Enum(IncentiveType), nullable=False)
    name = Column(Text, nullable=False)
    amount = Column(Integer, nullable=True)
    vendor = Column(Text, nullable=False)
    design_asset = Column(Enum(IncentiveDesignAsset), nullable=False)
    active = Column(Boolean, nullable=False)

    incentive_organizations = relationship("IncentiveOrganization")

    def __repr__(self) -> str:
        return f"<Incentive {self.id} - {self.name}>"


class IncentiveOrganization(base.TimeLoggedModelBase):
    __tablename__ = "incentive_organization"
    id = Column(Integer, primary_key=True)

    # We will remove the FK to organization KICK-1503
    organization_id = Column(BigInteger, ForeignKey("organization.id"), nullable=False)
    organization = relationship("Organization")

    incentive_id = Column(BigInteger, ForeignKey("incentive.id"), nullable=False)
    incentive = relationship("Incentive")

    action = Column(Enum(IncentiveAction), nullable=False)
    track_name = Column(String(120), nullable=False)

    countries = relationship(
        "IncentiveOrganizationCountry", cascade="all, delete-orphan"
    )

    active = Column(Boolean, nullable=False)

    @validates("track_name")
    def validate_track_name(self, _key, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value == "None":
            raise ValueError("Track can not be None")
        if value and not TrackName.isvalid(value):
            raise ValueError(f"'{value}' is not a valid track name")
        return value

    @validates("countries")
    def validate_country_codes(self, key, incentive_org_country):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        country_code = incentive_org_country.country_code
        validate_country_code(country_code)
        return incentive_org_country

    def __repr__(self) -> str:
        return f"<IncentiveOrg {self.id} [{self.organization.name} - {self.incentive.name}]>"


class IncentiveOrganizationCountry(base.ModelBase):
    __tablename__ = "incentive_organization_country"
    constraints = (UniqueConstraint("incentive_organization_id", "country_code"),)
    id = Column(Integer, primary_key=True)
    incentive_organization_id = Column(Integer, ForeignKey("incentive_organization.id"))
    incentive_organization = relationship("IncentiveOrganization")
    country_code = Column(String(2), nullable=False, unique=True)

    @property
    def country_name(self) -> str:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        countries_repo = geography_repository.CountryRepository()
        country = countries_repo.get(country_code=self.country_code)
        return country.name  # type: ignore[union-attr] # Item "None" of "Optional[Country]" has no attribute "name"

    @validates("country_code")
    def validate_country_codes(self, key, country_code):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return validate_country_code(country_code)

    def __repr__(self) -> str:
        return f"{self.country_name}"
