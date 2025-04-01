from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from models.base import ModelBase, TimeLoggedSnowflakeModelBase
from utils.log import logger
from wallet.models.constants import ReimbursementRequestSourceUploadSource

log = logger(__name__)


class ReimbursementRequestSource(TimeLoggedSnowflakeModelBase):
    """
    Each ReimbursementRequestSource is a receipt. A receipt can be associated with many requests
    and requests can have many receipts. They are joined to requests through the
    ReimbursementRequestSourceRequests model.
    """

    __tablename__ = "reimbursement_request_source"
    constraints = (UniqueConstraint("user_asset_id", "reimbursement_wallet_id"),)
    user_asset_id = Column(
        BigInteger,
        ForeignKey("user_asset.id"),
        nullable=True,
        doc="id of an uploaded image or pdf, a user asset source.",
    )
    document_mapping_uuid = Column(
        String(50),
        nullable=True,
        doc="A reference to the document mapping the reimbursement request source is associated with",
    )
    user_asset = relationship("UserAsset")
    reimbursement_wallet_id = Column(
        BigInteger, ForeignKey("reimbursement_wallet.id"), nullable=True
    )
    upload_source = Column(Enum(ReimbursementRequestSourceUploadSource))
    wallet = relationship("ReimbursementWallet", backref="sources")

    @hybrid_property
    def request_count(self):
        return len(self.reimbursement_requests)

    @request_count.expression  # type: ignore[no-redef] # Name "request_count" already defined on line 32
    def request_count(cls):
        return (
            select([func.count("*")])
            .where(
                ReimbursementRequestSourceRequests.reimbursement_request_source_id
                == cls.id
            )
            .label("request_count")
        )

    @property
    def type(self) -> str:
        return "user_asset"

    @property
    def source_id(self) -> int | None:
        return self.user_asset_id

    def __repr__(self) -> str:
        return f"<ReimbursementRequestSource[{self.id}] wallet={self.reimbursement_wallet_id}>"


class ReimbursementRequestSourceRequests(ModelBase):
    """
    Join table for requests and sources
    """

    __tablename__ = "reimbursement_request_source_requests"
    reimbursement_request_id = Column(
        Integer,
        ForeignKey("reimbursement_request.id"),
        primary_key=True,
        nullable=False,
    )
    request = relationship("ReimbursementRequest")
    reimbursement_request_source_id = Column(
        Integer,
        ForeignKey("reimbursement_request_source.id"),
        primary_key=True,
        nullable=False,
    )
    source = relationship("ReimbursementRequestSource")
