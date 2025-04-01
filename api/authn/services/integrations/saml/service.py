from __future__ import annotations

import dataclasses
import os
from typing import TypedDict

import ddtrace
from onelogin.saml2 import auth, idp_metadata_parser

from authn.services.integrations.saml import error, model, translate

__all__ = (
    "OneLoginSAMLVerificationService",
    "SAMLRequestBody",
    "get_onelogin_configuration",
    "OneLoginSAMLConfiguration",
)

from models.enterprise import ExternalIDPNames


class OneLoginSAMLVerificationService:
    """Verification Service for SAML requests using OneLogin."""

    __slots__ = (
        "configuration",
        "idp_metadata",
        "idp_settings",
        "_onelogin_settings",
    )

    def __init__(
        self,
        *,
        configuration: OneLoginSAMLConfiguration | None = None,
    ):
        self.configuration = configuration or get_onelogin_configuration()
        self._onelogin_settings = self._get_onelogin_settings()
        self.idp_settings = {
            idp: self._parse_idp_settings(m)
            for idp, m in self.configuration.idp_metadata.items()
        }

    def __repr__(self) -> str:
        return (
            "<"
            f"{self.__class__.__name__}("
            f"entity_id={self.configuration.entity_id!r}, "
            f"redirect_endpoint={self.configuration.redirect_endpoint!r}, "
            f"strict={self.configuration.strict!r}, "
            f"debug={self.configuration.debug!r}"
            ")>"
        )

    def add_idp(self, idp: str, metadata: str) -> None:
        """Add an Identity Provider to this services."""
        self.idp_settings[idp] = self._parse_idp_settings(metadata)

    def _parse_idp_settings(self, metadata: str) -> dict:
        settings = idp_metadata_parser.OneLogin_Saml2_IdPMetadataParser.parse(metadata)
        return {**settings, **self._onelogin_settings}

    @property
    def available_idps(self) -> tuple[str, ...]:
        """All the supported Identity Providers for this service."""
        return (*self.idp_settings,)

    @ddtrace.tracer.wrap()
    def parse_assertion(self, request: SAMLRequestBody) -> model.SAMLAssertion:
        """Parse a SAMLRequestBody into a valid SAMLAssertion."""
        idp, auth_object = self.process_request(request=request)
        assertion = self.parse_auth_object(idp=idp, auth_object=auth_object)
        return assertion

    @ddtrace.tracer.wrap()
    def process_request(
        self, request: SAMLRequestBody
    ) -> tuple[str, auth.OneLogin_Saml2_Auth]:
        auth_errors = {}
        # For every supported idp
        for idp, idp_settings in self.idp_settings.items():
            with ddtrace.tracer.trace(f"parse_{idp.lower()}"):
                # Process the SAML request
                auth_object = auth.OneLogin_Saml2_Auth(request, idp_settings)
                error_message = auth_object.process_response()
                # If authenticated, return a valid assertion
                if auth_object.is_authenticated():
                    return idp, auth_object
                auth_errors[idp.lower()] = {
                    "message": error_message,
                    "reason": auth_object.get_last_error_reason(),
                    "codes": auth_object.get_errors(),
                }
        raise error.SAMLVerificationError(
            "Failed to validate SAML request with available Identity Providers. "
            f"Tried: {self.available_idps}",
            auth_errors=auth_errors,  # type: ignore[arg-type] # Argument "auth_errors" to "SAMLVerificationError" has incompatible type "Dict[Any, Dict[str, Any]]"; expected "Dict[str, _AuthErrorDetail]"
            configuration=self.configuration,
        )

    @ddtrace.tracer.wrap()
    def parse_auth_object(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, *, idp: str, auth_object: auth.OneLogin_Saml2_Auth, **mapping
    ) -> model.SAMLAssertion:
        return translate.response_to_assertion(
            idp=idp, response=auth_object, configuration=self.configuration, **mapping
        )

    def _get_onelogin_settings(self) -> dict:
        # Pre-defined generalized structure for our OneLogin SAML settings
        return {
            "strict": self.configuration.strict,
            "debug": self.configuration.debug,
            "sp": {
                "entityId": self.configuration.entity_id,
                "assertionConsumerService": {
                    "url": self._get_redirect_url(),
                    "binding": self.configuration.binding,
                },
                "NameIDFormat": self.configuration.name_format,
                "x509cert": self.configuration.saml_cert,
                "privateKey": self.configuration.private_key,
            },
        }

    def _get_redirect_url(self) -> str:
        # FIXME: Figure out how to remove runtime Flask app-context dependency here.
        from flask import url_for

        return url_for(
            self.configuration.redirect_endpoint,
            _external=True,
            _scheme="https",
        )


@dataclasses.dataclass
class OneLoginSAMLConfiguration:
    entity_id: str
    saml_cert: str
    private_key: str
    redirect_endpoint: str
    strict: bool = True
    debug: bool = True
    binding: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    name_format: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    idp_metadata: dict = dataclasses.field(default_factory=dict)


def get_onelogin_configuration(**metadata) -> OneLoginSAMLConfiguration:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    """Build the configuration for our OneLogin integration from the environment."""
    # Search the environment for SAML metadata for our known external IDPs.
    if not metadata:
        for name in ExternalIDPNames:
            var = f"SAML_METADATA_{name.name}"
            if var not in os.environ:
                continue
            metadata[name.value] = os.environ[var]

    return OneLoginSAMLConfiguration(
        entity_id=os.environ.get("BASE_URL", _DEFAULT_BASE_URL) + "/",
        redirect_endpoint=os.environ.get(
            "SAML_REDIRECT_ENDPOINT", _DEFAULT_REDIRECT_ENDPOINT
        ),
        saml_cert=os.environ.get("SAML_CERT", ""),
        private_key=os.environ.get("SAML_PRIVATE", ""),
        strict=os.environ.get("SAML_STRICT", True),  # type: ignore[arg-type] # Argument "strict" to "OneLoginSAMLConfiguration" has incompatible type "Union[str, bool]"; expected "bool"
        debug=os.environ.get("SAML_DEBUG", True),  # type: ignore[arg-type] # Argument "debug" to "OneLoginSAMLConfiguration" has incompatible type "Union[str, bool]"; expected "bool"
        binding=os.environ.get("SAML_BINDING", _DEFAULT_BINDING),
        name_format=os.environ.get("SAML_NAME_FORMAT", _DEFAULT_NAME_FORMAT),
        idp_metadata=metadata,
    )


# Static default values
_DEFAULT_BASE_URL = "https://www.mavenclinic.com"
_DEFAULT_REDIRECT_ENDPOINT = "samlconsumerresource"
_DEFAULT_BINDING = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
_DEFAULT_NAME_FORMAT = "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified"


class SAMLRequestBody(TypedDict):
    https: str
    http_host: str
    server_port: int | None
    script_name: str
    get_data: dict[str, str]
    post_data: dict[str, str]
