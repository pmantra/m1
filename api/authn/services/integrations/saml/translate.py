from __future__ import annotations

from typing import TypeVar

import ddtrace
from onelogin.saml2 import auth

from authn.services.integrations.saml import error, model, service

__all__ = ("response_to_assertion",)


@ddtrace.tracer.wrap()
def response_to_assertion(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    idp: str,
    response: auth.OneLogin_Saml2_Auth,
    configuration: service.OneLoginSAMLConfiguration,
    **mapping,
) -> model.SAMLAssertion:
    """Translate a SAML response from OneLogin to a normalized Assertion."""

    issuer = response.get_settings().get_idp_data()["entityId"]
    subject = response.get_nameid()
    attributes = response.get_attributes()
    kwargs = {key: _extract(field, attributes) for key, field in mapping.items()}
    missing = (*(k for k in _REQUIRED_FIELDS if not kwargs[k]),)
    if missing:
        raise error.SAMLTranslationError(
            f"Failed to translate SAML response. Detail: Failed to extract fields: {missing}.",
            configuration=configuration,
            auth_object=response,
        )
    kwargs["email"] = kwargs["email"].lower()
    assertion = model.SAMLAssertion(
        idp=str(idp),
        issuer=issuer,
        subject=subject,
        **kwargs,
    )
    return assertion


_REQUIRED_FIELDS = frozenset(("email", "employee_id", "organization_external_id"))

_AT = TypeVar("_AT", bound=dict)


def _extract(key: str, attributes: _AT) -> str:
    value = attributes.get(key)
    if not value:
        return ""
    return value[0].strip()
