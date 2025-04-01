from __future__ import annotations

from typing import Optional

from authn.models.user import User
from messaging.services.zendesk import SynchronizedZendeskTicket


class BasePaymentOpsZendeskTicket(SynchronizedZendeskTicket):
    HEADER_PREFIX = "Payment Ops Action Required: "
    DEFAULT_TAGS = ["payment_ops", "action_required"]

    def __init__(self, user: User, wallet_id: int) -> None:
        super().__init__()
        self.user = user
        self.wallet_id = wallet_id

    @property
    def recorded_ticket_id(self) -> None:
        return None  # We don't store this ticket ID

    @recorded_ticket_id.setter
    def recorded_ticket_id(self, ticket_id: str) -> None:
        pass  # We don't need to store this ticket ID

    def record_comment_id(self, comment_id: str) -> None:
        pass  # We don't need to store the comment ID

    @property
    def desired_ticket_requester(self) -> User:
        return self.user

    @property
    def desired_ticket_status(self) -> str:
        return "open"

    @property
    def comment_public(self) -> bool:
        return False

    @property
    def comment_author(self) -> User:
        return self.user

    @property
    def user_id(self) -> Optional[int]:
        return self.user.id if self.user is not None else None

    @property
    def is_internal(self) -> bool:
        return True

    @property
    def is_wallet(self) -> bool:
        return True

    @property
    def user_need_when_solving_ticket(self) -> str:
        return "customer-need-member-proactive-outreach-other"

    ## Implementations must add the following:

    @property
    def desired_ticket_subject(self) -> str:
        raise NotImplementedError()

    @property
    def desired_ticket_tags(self) -> list[str]:
        raise NotImplementedError()

    @property
    def comment_body(self) -> str:
        raise NotImplementedError()


class GenericPaymentOpsZendeskTicket(BasePaymentOpsZendeskTicket):
    HEADER = BasePaymentOpsZendeskTicket.HEADER_PREFIX

    def __init__(
        self, user: User, wallet_id: int, details: Optional[str], tag: Optional[str]
    ) -> None:
        super().__init__(user=user, wallet_id=wallet_id)
        self.details = details
        self.tag = tag

    @property
    def desired_ticket_subject(self) -> str:
        return self.HEADER + f" - User {self.user.id}"

    @property
    def desired_ticket_tags(self) -> list[str]:
        tags = BasePaymentOpsZendeskTicket.DEFAULT_TAGS.copy()
        if self.tag:
            tags.append(self.tag)
        return tags

    def comment_body(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return f"""
{self.HEADER}

User: {self.user.full_name} (ID: {self.user.id})
Wallet ID: {self.wallet_id}

Details:
{self.details or 'No additional details provided'}

Please investigate and take appropriate action.
"""


class ROSChangePaymentOpsZendeskTicket(BasePaymentOpsZendeskTicket):
    HEADER = BasePaymentOpsZendeskTicket.HEADER_PREFIX + "Wallet ROS Change"

    def __init__(
        self, user: User, wallet_id: int, old_ros_id: int, new_ros_id: int
    ) -> None:
        super().__init__(user=user, wallet_id=wallet_id)
        self.old_ros_id = old_ros_id
        self.new_ros_id = new_ros_id

    @property
    def desired_ticket_subject(self) -> str:
        return self.HEADER + f" - User {self.user.id}"

    @property
    def desired_ticket_tags(self) -> list[str]:
        tags = BasePaymentOpsZendeskTicket.DEFAULT_TAGS.copy()
        tags.append("wallet_ros_change")
        return tags

    @property
    def comment_body(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return f"""
{self.HEADER}

User: {self.user.full_name} (ID: {self.user.id})
Wallet ID: {self.wallet_id}

Old ROS ID: {self.old_ros_id}
New ROS ID: {self.new_ros_id}

Please update the wallet configuration in Alegeus and any other necessary systems.
"""


class NoEligibilityPaymentOpsZendeskTicket(BasePaymentOpsZendeskTicket):
    HEADER = BasePaymentOpsZendeskTicket.HEADER_PREFIX + "No Eligibility Record"

    def __init__(self, user: User, wallet_id: int, reason: str) -> None:
        super().__init__(user=user, wallet_id=wallet_id)
        self.reason = reason

    @property
    def desired_ticket_subject(self) -> str:
        return self.HEADER + f" - User {self.user.id}"

    @property
    def desired_ticket_tags(self) -> list[str]:
        tags = BasePaymentOpsZendeskTicket.DEFAULT_TAGS.copy()
        tags.append("no_eligibility_record")
        return tags

    @property
    def comment_body(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return f"""
{self.HEADER}

User: {self.user.full_name} (ID: {self.user.id})
Wallet ID: {self.wallet_id}

Reason: {self.reason or 'No eligibility record found'}

Please investigate the eligibility status for this user and take appropriate action.
"""


class SyncCreditPaymentOpsZendeskTicket(BasePaymentOpsZendeskTicket):
    HEADER = BasePaymentOpsZendeskTicket.HEADER_PREFIX + "Failed to Deduct Credits"

    def __init__(
        self, user: User, wallet_id: int, reimbursement_request_id: int, reason: str
    ) -> None:
        super().__init__(user=user, wallet_id=wallet_id)
        self.reimbursement_request_id = reimbursement_request_id
        self.reason = reason

    @property
    def desired_ticket_subject(self) -> str:
        return self.HEADER + f" - User {self.user.id}"

    @property
    def desired_ticket_tags(self) -> list[str]:
        tags = BasePaymentOpsZendeskTicket.DEFAULT_TAGS.copy()
        tags.append("sync_claims_credit_failure")
        return tags

    @property
    def comment_body(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return f"""
{self.HEADER}

Wallet ID: {self.wallet_id}
Reimbursement Request ID: {self.reimbursement_request_id}

Reason: {self.reason}

Please investigate the wallet and reimbursement request and take appropriate action.
The cycle credits for theis reimbursement request probably need to be deducted manually.
"""


class SyncAccountSccPaymentOpsZendeskTicket(BasePaymentOpsZendeskTicket):
    HEADER = (
        BasePaymentOpsZendeskTicket.HEADER_PREFIX + "Failed to sync account and/or SCC"
    )

    def __init__(
        self,
        user: User,
        wallet_id: int,
        reimbursement_request_id: int,
        reimbursement_claim_id: int,
        reason: str,
        data: dict | None = None,
    ) -> None:
        super().__init__(user=user, wallet_id=wallet_id)
        self.reimbursement_request_id = reimbursement_request_id
        self.reimbursement_claim_id = reimbursement_claim_id
        self.reason = reason
        self.data = data or {}

    @property
    def desired_ticket_subject(self) -> str:
        return self.HEADER + f" - User {self.user.id}"

    @property
    def desired_ticket_tags(self) -> list[str]:
        tags = BasePaymentOpsZendeskTicket.DEFAULT_TAGS.copy()
        tags.append("sync_account_scc_failure")
        return tags

    @property
    def comment_body(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        body = f"""
{self.HEADER}

This reimbursement claim was synced back from Alegeus but the Category, Expense Type, and/or SCC
could not be updated due to the following error:
{self.reason}

The category, expense type, or SCC for this reimbursement request may need to be adjusted manually.

Wallet ID: {self.wallet_id}
Reimbursement Request ID: {self.reimbursement_request_id}
Reimbursement Claim ID: {self.reimbursement_claim_id}

"""

        for k in self.data:
            body += f"{k}: {self.data[k]}\n"

        return body
