import datetime

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
)
from sqlalchemy.orm import relationship

from models.base import ModelBase
from wallet.models.constants import (
    ReimbursementRequestState,
    WalletReportConfigCadenceTypes,
    WalletReportConfigColumnTypes,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.services.wallet_client_reporting_constants import (
    WalletReportConfigFilterType,
)


class WalletClientReports(ModelBase):
    __tablename__ = "wallet_client_reports"

    id = Column("id", BigInteger, autoincrement=True, primary_key=True)

    organization_id = Column(BigInteger, ForeignKey("organization.id"), nullable=False)
    organization = relationship("Organization")
    configuration_id = Column(
        Integer, ForeignKey("wallet_client_report_configuration_v2.id"), nullable=False
    )
    configuration = relationship(
        "WalletClientReportConfiguration",
        primaryjoin="WalletClientReports.configuration_id==WalletClientReportConfiguration.id",
    )
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    client_submission_date = Column(Date, nullable=True)
    client_approval_date = Column(Date, nullable=True)
    peakone_sent_date = Column(Date, nullable=True)
    payroll_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
    )

    reimbursement_requests = relationship(
        ReimbursementRequest,
        secondary="wallet_client_report_reimbursements",
        backref="wallet_client_report",
    )


class WalletClientReportConfiguration(ModelBase):
    __tablename__ = "wallet_client_report_configuration_v2"
    id = Column("id", Integer, autoincrement=True, primary_key=True)

    organization_id = Column(BigInteger, ForeignKey("organization.id"), nullable=False)
    organization = relationship(
        "Organization", backref="wallet_client_report_configuration", uselist=False
    )
    cadence = Column(Enum(WalletReportConfigCadenceTypes), nullable=False)
    day_of_week = Column(Integer, nullable=True, default=1)
    columns = relationship(
        "WalletClientReportConfigurationReportTypes",
        secondary="wallet_client_report_configuration_report_columns_v2",
        uselist=True,
    )
    filters = relationship(
        "WalletClientReportConfigurationFilter",
        back_populates="configuration",
        cascade="all, delete",
    )

    def column_names(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        names = [col.column_type.name for col in self.columns]  # type: ignore[attr-defined] # "str" has no attribute "name"
        return names

    def __repr__(self) -> str:
        return f"Config:{self.id} {self.organization.name}"


class WalletClientReportConfigurationFilter(ModelBase):
    __tablename__ = "wallet_client_report_configuration_filter"
    id = Column("id", Integer, autoincrement=True, primary_key=True)

    configuration_id = Column(
        Integer, ForeignKey("wallet_client_report_configuration_v2.id"), nullable=False
    )
    configuration = relationship(
        "WalletClientReportConfiguration", back_populates="filters"
    )
    filter_type = Column(Enum(WalletReportConfigFilterType), nullable=False)
    filter_value = Column(String, nullable=False)
    equal = Column(Boolean, default=True)

    def __repr__(self) -> str:
        if self.equal:
            return f"{self.filter_type} is {self.filter_value}"
        return f"{self.filter_type} is not {self.filter_value}"


class WalletClientReportReimbursements(ModelBase):
    __tablename__ = "wallet_client_report_reimbursements"
    id = Column("id", Integer, autoincrement=True, primary_key=True)

    reimbursement_request_id = Column(
        BigInteger,
        ForeignKey("reimbursement_request.id"),
        nullable=False,
        primary_key=True,
    )
    reimbursement_request = relationship(ReimbursementRequest)
    wallet_client_report_id = Column(
        BigInteger, ForeignKey("wallet_client_reports.id"), nullable=False
    )
    wallet_client_report = relationship(WalletClientReports)
    peakone_sent_date = Column(Date, nullable=True)
    reimbursement_request_state = Column(
        Enum(ReimbursementRequestState),
        nullable=False,
        server_default="APPROVED",
    )


class WalletClientReportConfigurationReportTypes(ModelBase):
    __tablename__ = "wallet_client_report_configuration_report_types"
    id = Column(Integer, autoincrement=True, primary_key=True)

    column_type = Column(Enum(WalletReportConfigColumnTypes), nullable=False)

    def __repr__(self) -> str:
        return f"<WalletClientReportConfigurationReportTypes: {self.column_type.name}>"  # type: ignore[attr-defined] # "str" has no attribute "name"


class WalletClientReportConfigurationReportColumns(ModelBase):
    __tablename__ = "wallet_client_report_configuration_report_columns_v2"

    wallet_client_report_configuration_id = Column(
        BigInteger,
        ForeignKey("wallet_client_report_configuration_v2.id"),
        nullable=False,
        primary_key=True,
    )
    wallet_client_report_configuration_report_type_id = Column(
        Integer,
        ForeignKey("wallet_client_report_configuration_report_types.id"),
        nullable=False,
        primary_key=True,
    )
