from __future__ import annotations

from typing import TypedDict

from onelogin.saml2 import auth

from authn.domain import model, repository


def migrate_field_mappings(*, commit: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    idps = repository.IdentityProviderRepository()
    field_aliases = repository.IDPFieldAliasRepository()
    mappings = fetch_field_mappings(repo=idps)
    saved = save_field_mappings(repo=field_aliases, mappings=mappings, commit=commit)
    return saved


def fetch_field_mappings(
    repo: repository.IdentityProviderRepository,
) -> list[model.IdentityProviderFieldAlias]:
    mappings = []
    for idp_name, mapping in _IDP_FIELD_MAPPINGS.items():
        idp = repo.get_by_name(name=idp_name)
        if idp is None:
            continue
        mappings.extend(
            model.IdentityProviderFieldAlias(
                field=f, alias=a, identity_provider_id=idp.id  # type: ignore[arg-type] # Argument "alias" to "IdentityProviderFieldAlias" has incompatible type "object"; expected "str"
            )
            for f, a in mapping.items()
        )
    return mappings


def save_field_mappings(
    repo: repository.IDPFieldAliasRepository,
    mappings: list[model.IdentityProviderFieldAlias],
    *,
    commit: bool = True,
) -> list[model.IdentityProviderFieldAlias]:
    saved = [repo.create(instance=m) for m in mappings]
    if commit:
        repo.session.commit()
    return saved


def _get_idp_field_mapping(
    idp: str, response: auth.OneLogin_Saml2_Auth
) -> _IDPFieldMap:
    if idp not in _IDP_FIELD_MAPPINGS:
        raise ValueError(
            f"Failed to translate SAML response. Detail: Unknown Identity Provider ({idp})",
            response,
        )
    mapping = _IDP_FIELD_MAPPINGS[idp]
    return mapping


class _IDPFieldMap(TypedDict):
    email: str
    first_name: str
    last_name: str
    employee_id: str
    rewards_id: str
    organization_external_id: str


_IDP_FIELD_MAPPINGS: dict[str, _IDPFieldMap] = {
    "VIRGIN_PULSE": _IDPFieldMap(
        email="EmailAddress",
        first_name="firstname",
        last_name="lastname",
        employee_id="EmployeeID",
        rewards_id="MemberID",
        organization_external_id="SponsorID",
    ),
    "OKTA": _IDPFieldMap(
        email="Email",
        first_name="FirstName",
        last_name="LastName",
        employee_id="MemberId",
        rewards_id="VirginPulseID",
        organization_external_id="OrgId",
    ),
    "CASTLIGHT": _IDPFieldMap(
        email="email",
        first_name="firstName",
        last_name="lastName",
        employee_id="subscriberEmployeeId",
        rewards_id="castlightUserGuid",
        organization_external_id="employerKey",
    ),
}
