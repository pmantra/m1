from __future__ import annotations

import datetime
from typing import List

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from models.base import TimeLoggedSnowflakeModelBase
from wallet.models.constants import ChangeType, SyncIndicator, WalletState


class ReimbursementWalletEligibilitySyncMeta(TimeLoggedSnowflakeModelBase):
    """
    Tracks changes to wallet eligibility state and ROS assignments.
    This table records history of syncs with eligibility system and changes made to wallets.
    """

    __tablename__ = "reimbursement_wallet_eligibility_sync_meta"

    # Foreign key to the wallet this sync record is for
    wallet_id = Column(
        BigInteger,
        ForeignKey("reimbursement_wallet.id"),
        nullable=False,
        doc="ID of the wallet this sync record is associated with",
    )
    wallet = relationship("ReimbursementWallet")

    # When the sync occurred
    sync_time = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
        doc="Timestamp when this sync occurred",
    )

    # What initiated the sync
    sync_initiator = Column(
        Enum(SyncIndicator),
        nullable=False,
        default=SyncIndicator.CRON_JOB,
        doc="What initiated this sync (e.g. CRON_JOB, MANUAL)",
    )

    # Type of change that occurred
    change_type = Column(
        Enum(ChangeType),
        nullable=False,
        doc="Type of change that occurred (e.g. ROS_CHANGE, DISQUALIFIED, RUNOUT)",
    )

    # Previous/latest end dates for eligibility
    previous_end_date = Column(
        DateTime,
        nullable=True,
        doc="Previous eligibility end date before this sync",
    )
    latest_end_date = Column(
        DateTime,
        nullable=True,
        doc="Latest eligibility end date after this sync",
    )

    # ROS IDs before/after change
    previous_ros_id = Column(
        Integer,
        nullable=False,
        doc="ID of the ROS before any changes",
    )
    latest_ros_id = Column(
        Integer,
        nullable=True,
        doc="ID of the ROS after changes",
    )

    # User associations
    user_id = Column(
        Integer,
        nullable=False,
        doc="ID of the primary user (employee) associated with this wallet",
    )

    # Store dependent IDs as comma-separated string
    _dependents_ids = Column(
        "dependents_ids",
        String(4096),
        nullable=False,
        default="",
        doc="Comma-separated list of dependent user IDs associated with this wallet",
    )

    # Flags
    is_dry_run = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether this was a dry run sync that didn't persist changes",
    )

    # Previous wallet state
    previous_wallet_state = Column(
        Enum(WalletState),
        nullable=True,
        default=WalletState.QUALIFIED,
        doc="State of the wallet before any changes",
    )

    @hybrid_property
    def dependents_ids(self) -> List[int]:
        """Convert comma-separated string of IDs to list of integers."""
        if not self._dependents_ids:
            return []
        return [int(x) for x in self._dependents_ids.split(",") if x]

    @dependents_ids.setter  # type: ignore[no-redef]
    def dependents_ids(self, value: List[int]) -> None:
        """Convert list of integers to comma-separated string."""
        if not value:
            self._dependents_ids = ""
        else:
            self._dependents_ids = ",".join(str(x) for x in value)

    def __repr__(self) -> str:
        return (
            f"<ReimbursementWalletEligibilitySyncMeta "
            f"wallet_id={self.wallet_id} "
            f"change_type={self.change_type} "
            f"sync_time={self.sync_time}>"
        )
