from __future__ import annotations

from sqlalchemy import Column, FetchedValue, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models import base


class ExternalIdentity(base.TimeLoggedSnowflakeModelBase):
    """DEPRECATED
    replaced by UserExternalIdentity.

    Provides a way to uniquely look up and identify a user in our system based on the
    information given to us through SAML assertions.
    """

    __tablename__ = "external_identity"

    idp = Column(
        String(120),
        nullable=False,
        doc="Populated by the issuer value sent back in SAML assertions.",
    )
    identity_provider_id = Column(
        Integer, server_default=FetchedValue(), server_onupdate=FetchedValue()
    )
    external_user_id = Column(
        String(120),
        nullable=False,
        doc="Populated by the subject value sent back in SAML assertions. A "
        "guaranteed stable and unique identifier per IdP.",
    )
    external_organization_id = Column(
        String(120), server_default=FetchedValue(), server_onupdate=FetchedValue()
    )
    rewards_id = Column(
        String(120),
        unique=True,
        doc="Uniquely identifies users who are part of rewards programs. Used to "
        "grant users points and rewards for those programs.",
    )

    unique_corp_id = Column(
        String(120),
        doc="The ID delivered by the IDP for us to use to find the correct OrganizationEmployee",
    )

    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    user = relationship("User", backref="external_identities")

    organization_id = Column(Integer, ForeignKey("organization.id"))
    organization = relationship("Organization")
