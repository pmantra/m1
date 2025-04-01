import enum

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from models.base import TimeLoggedExternalUuidModelBase
from wallet.models.constants import PatientInfertilityDiagnosis
from wallet.models.member_benefit import MemberBenefit
from wallet.models.reimbursement import ReimbursementRequestCategory
from wallet.models.reimbursement_wallet_benefit import ReimbursementWalletBenefit
from wallet.models.reimbursement_wallet_global_procedures import (
    ReimbursementWalletGlobalProcedures,
)


class TreatmentProcedureStatus(enum.Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    CANCELLED = "CANCELLED"


class TreatmentProcedureType(enum.Enum):
    MEDICAL = "MEDICAL"
    PHARMACY = "PHARMACY"


class TreatmentProcedure(TimeLoggedExternalUuidModelBase):
    __tablename__ = "treatment_procedure"

    member_id = Column(
        BigInteger,
        nullable=False,
        doc="References the user.id of the member. "
        "We do not use a foreign key constraint to avoid "
        "tight-coupling in the database.",
    )
    infertility_diagnosis = Column(Enum(PatientInfertilityDiagnosis), nullable=True)
    reimbursement_wallet_id = Column(BigInteger, nullable=False)
    reimbursement_request_category_id = Column(
        BigInteger, ForeignKey("reimbursement_request_category.id"), nullable=False
    )
    fee_schedule_id = Column(BigInteger, ForeignKey("fee_schedule.id"), nullable=False)
    # deprecated
    reimbursement_wallet_global_procedures_id = Column(
        BigInteger,
        ForeignKey("reimbursement_wallet_global_procedures.id"),
        nullable=True,
        doc="Deprecated in favor of global procedure service",
    )
    fertility_clinic_id = Column(
        BigInteger, ForeignKey("fertility_clinic.id"), nullable=False
    )
    fertility_clinic_location_id = Column(
        BigInteger, ForeignKey("fertility_clinic_location.id"), nullable=False
    )
    cost_breakdown_id = Column(Integer, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    procedure_name = Column(String(191), nullable=False)
    procedure_type = Column(
        "type",
        Enum(TreatmentProcedureType),
        nullable=False,
        default=TreatmentProcedureType.MEDICAL,
    )
    cost = Column(Integer, nullable=False, doc="Cost of procedure in currency")
    """
    `cost` does not necessarily mean that currency was deducted from the
    member's balance for the procedure. `cost` simply shows the cost of the
    global procedure in currency at the time of the treatment.
    """
    cost_credit = Column(
        Integer,
        nullable=True,
        doc="Cost of procedure in credits only for cycle based procedures",
    )
    """
    Having a nonnull `cost_credit` does not necessarily mean that credits were 
    deducted from the member's balance for the procedure. `cost_credit` simply
    shows the cost of the procedure in credits of the global procedure at the
    time of the treatment.
    """
    status = Column(Enum(TreatmentProcedureStatus), nullable=False)
    cancellation_reason = Column(String(500), nullable=True)
    cancelled_date = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)
    global_procedure_id = Column(String(36), nullable=True)
    partial_procedure_id = Column(
        BigInteger, ForeignKey("treatment_procedure.id"), nullable=True
    )

    reimbursement_request_category = relationship(ReimbursementRequestCategory)
    fee_schedule = relationship("FeeSchedule")
    reimbursement_wallet_global_procedures = relationship(
        ReimbursementWalletGlobalProcedures
    )
    fertility_clinic = relationship("FertilityClinic")
    fertility_clinic_location = relationship("FertilityClinicLocation")
    partial_procedure = relationship(
        "TreatmentProcedure", backref="parent", remote_side="TreatmentProcedure.id"
    )
    user = relationship(
        "User",
        primaryjoin="TreatmentProcedure.member_id == User.id",
        foreign_keys="User.id",
        uselist=False,
    )

    reimbursement_wallet_benefit = relationship(
        ReimbursementWalletBenefit,
        primaryjoin="TreatmentProcedure.reimbursement_wallet_id == ReimbursementWalletBenefit.reimbursement_wallet_id",
        foreign_keys="ReimbursementWalletBenefit.reimbursement_wallet_id",
        uselist=False,
    )

    member_benefit = relationship(
        MemberBenefit,
        primaryjoin="TreatmentProcedure.member_id == MemberBenefit.user_id",
        foreign_keys="MemberBenefit.user_id",
        uselist=False,
    )
