import enum

from authn.models.user import User
from wallet.models.constants import WalletState


class WalletApprovalStatus(enum.Enum):
    PENDING = None
    QUALIFIED = True
    DISQUALIFIED = False

    def to_state(self) -> WalletState:
        return _WALLET_APPROVAL_TO_STATE[self]

    @classmethod
    def from_user(cls, user: User) -> "WalletApprovalStatus":
        # FIXME: Temporary hack to turn off pre-approval flow (ch4680)
        return cls.PENDING


# This is order-dependent
_WALLET_APPROVAL_TO_STATE = dict(zip(WalletApprovalStatus, WalletState))


class ClientLayout(str, enum.Enum):
    """Tells client devices which member dashboard layout to show."""

    MEMBER = "MEMBER"
    """The member has responsibility for at least 1 upcoming payment."""

    FULLY_COVERED = "FULLY_COVERED"
    """The procedure has been fully covered by cycles or credits and insurance. The patient never had any financial responsibility."""

    NO_PAYMENTS = "NO_PAYMENTS"
    """No payments due on the procedure."""

    ZERO_CURRENCY = "ZERO_CURRENCY"
    """No currency remaining in the currency-based category."""

    ZERO_CYCLES = "ZERO_CYCLES"
    """No credits remaining in the cycle-based category."""

    PENDING_COST = "PENDING_COST"
    """The cost breakdown is pending calculation. This period should not last more than a few minutes if it occurs."""

    RUNOUT = "RUNOUT"
    """The member has 90 days to submit old receipts"""


class TreatmentVariant(str, enum.Enum):
    NONE = "NONE"
    IN_TREATMENT = "IN_TREATMENT"
