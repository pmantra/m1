from __future__ import annotations

from dataclasses import dataclass

from authn.models.user import User
from models.enterprise import Organization
from storage.connection import db
from utils.log import logger

log = logger(__name__)


@dataclass
class InboundPhoneNumberInfo:
    user: User
    org_id: int | None = None
    user_id: int | None = None

    def __post_init__(self) -> None:

        # validate user_id
        if not self.user_id:
            raise ValueError("Missing required query parameter 'user_id'")
        if not self.org_id:
            raise ValueError("Missing required query parameter 'org_id'")
        if self.user.id != self.user_id:
            log.error(
                "User ID passed in does not match authenticated user",
                authenticated_user_id=self.user.id,
                passed_user_id=self.user_id,
            )
            raise ValueError("Invalid 'user_id'")
        organization = self.user.organization_v2
        if not organization:
            raise AttributeError("User does not have an organization")
        confirmed_organization = db.session.query(Organization).get(self.org_id)
        if not confirmed_organization:
            raise AttributeError("Organization does not exist")
        if self.org_id != organization.id:
            raise AttributeError(
                "Given organization ID does not match user organization ID"
            )
