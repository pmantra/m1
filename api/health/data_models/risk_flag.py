import enum
from typing import List

from sqlalchemy import Boolean, Column, Enum, Integer, String
from sqlalchemy.orm import synonym

from models import base


class RiskFlagSeverity(enum.Enum):
    NONE = "NONE"
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"


# enums used by Care Programs in the CPS service
class ECPQualifierType(enum.Enum):
    RISK = "RISK"
    CONDITION = "CONDITION"
    COMPOSITE = "COMPOSITE"


class ECPProgramQualifiers(enum.Enum):
    MENTAL_HEALTH = "MENTAL_HEALTH"
    CHRONIC_CONDITIONS = "CHRONIC_CONDITIONS"


class RiskFlag(base.TimeLoggedModelBase):
    __tablename__ = "risk_flag"

    def __repr__(self) -> str:
        return f"<RiskFlag[{self.id}]: Name: {self.name} Type: {self.severity}>"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False, unique=True)
    severity = Column(Enum(RiskFlagSeverity), nullable=False)
    ecp_qualifier_type = Column(Enum(ECPQualifierType))
    ecp_program_qualifier = Column(Enum(ECPProgramQualifiers))
    is_mental_health = Column(Boolean, default=False, nullable=False)
    # is_chronic_condition should be deleted soon, use is_physical_health instead
    is_chronic_condition = Column(Boolean, default=False, nullable=False)
    is_physical_health = Column(Boolean, default=False, nullable=False)
    is_utilization = Column(Boolean, default=False, nullable=False)
    is_situational = Column(Boolean, default=False, nullable=False)
    is_ttc_and_treatment = Column(Boolean, default=False, nullable=False)

    relevant_to_maternity = Column(
        "relevant_to_materity", Boolean, default=False, nullable=False
    )
    relevant_to_fertility = Column(Boolean, default=False, nullable=False)

    uses_value = Column(Boolean, default=False, nullable=False)
    # value_unit should be the plural term (cycles, months, attempts, etc)
    value_unit = Column(String(32), default=None, nullable=True)

    @property
    def is_risk_stratification_flag(self) -> bool:
        return self.severity is not RiskFlagSeverity.NONE

    # synonym to allows field usages by their older
    type = synonym("severity")
    ecp_flag_type = synonym("ecp_qualifier_type")

    def is_track_relevant(self, track_names: List[str]) -> bool:
        from models.tracks.track import TrackName

        if self.relevant_to_maternity:
            if TrackName.PREGNANCY in track_names:
                return True
            if TrackName.POSTPARTUM in track_names:
                return True
        if self.relevant_to_fertility:
            if TrackName.FERTILITY in track_names:
                return True
        return False
