import dataclasses

__all__ = ("SAMLAssertion",)


@dataclasses.dataclass
class SAMLAssertion:
    __slots__ = (
        "idp",
        "issuer",
        "subject",
        "email",
        "first_name",
        "last_name",
        "employee_id",
        "rewards_id",
        "organization_external_id",
    )
    idp: str
    issuer: str
    subject: str
    email: str
    first_name: str
    last_name: str
    employee_id: str
    rewards_id: str
    organization_external_id: str
