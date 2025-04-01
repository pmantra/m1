from __future__ import annotations

__all__ = (
    "SAMLIntegrationError",
    "SAMLTranslationError",
    "SAMLVerificationError",
)

from typing import TYPE_CHECKING, TypedDict

from onelogin.saml2 import auth

if TYPE_CHECKING:
    from authn.services.integrations.saml import service


class SAMLIntegrationError(Exception):
    """Base error for all SAML Integration errors."""

    def __init__(
        self,
        message: str,
        configuration: service.OneLoginSAMLConfiguration,
        auth_object: auth.OneLogin_Saml2_Auth | None,
    ):
        self.auth_object = auth_object
        self.configuration = configuration
        super().__init__(message)


class SAMLVerificationError(SAMLIntegrationError, ValueError):
    """A generic error indicating that verification failed."""

    ...

    def __init__(
        self,
        message: str,
        auth_errors: dict[str, _AuthErrorDetail],
        configuration: service.OneLoginSAMLConfiguration,
    ):
        self.auth_errors = auth_errors
        self.configuration = configuration
        super().__init__(message, configuration=configuration, auth_object=None)


class _AuthErrorDetail(TypedDict):
    message: str
    reason: str
    codes: list[str]


class SAMLTranslationError(SAMLIntegrationError, ValueError):
    """A generic error indicating a problem with the received response."""

    ...
