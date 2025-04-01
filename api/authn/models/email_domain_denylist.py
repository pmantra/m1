from __future__ import annotations

from sqlalchemy import Column, Integer, String

from models import base


class EmailDomainDenylist(base.TimeLoggedModelBase):
    """
    A unique email domain name that users should not be allowed to register with
    """

    __tablename__ = "email_domain_denylist"

    id = Column(Integer, primary_key=True)
    domain = Column(String(180), nullable=False, unique=True)
