import os

import ddtrace
import jwt


class TokenValidator:
    """A JWT Bearer token validator"""

    def __init__(self) -> None:
        offline_enabled = os.getenv("OFFLINE_AUTH_ENABLED") in ["True", "true"]
        # Only in the development environment do we want to allow offline authentication
        if offline_enabled:
            self.decoder = DevelopmentDecoder()
        else:
            self.decoder = Decoder()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Decoder", variable has type "DevelopmentDecoder")

    def decode_token(self, bearer_header: str) -> dict:
        token = self._get_token_auth_header(bearer_header)
        try:
            return self.decoder.decode(token)
        except jwt.exceptions.InvalidTokenError:
            raise TokenValidationError("Failed to decode Bearer token")

    def get_token_expires_at(self, token: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if token:
            return self.decoder.get_expires_at(token)
        return None

    def _get_token_auth_header(self, bearer_header) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        """Obtains the Access Token from the Authorization Header"""
        if not bearer_header:
            raise TokenValidationError("Authorization header missing")

        parts = bearer_header.split()

        if parts[0].lower() != "bearer":
            raise TokenValidationError("Authorization header must start with 'Bearer'")
        elif len(parts) != 2:
            raise TokenValidationError("Authorization header must be a Bearer token")

        token = parts[1]
        return token


class Decoder:
    """A decoder for JWTs that verifies the signature agains our IDP's JWKS file"""

    def __init__(self, idp_domain: str = None, idp_audience: str = None):  # type: ignore[assignment] # Incompatible default for argument "idp_domain" (default has type "None", argument has type "str") #type: ignore[assignment] # Incompatible default for argument "idp_audience" (default has type "None", argument has type "str")
        self.idp_domain = idp_domain or os.getenv("AUTH0_DOMAIN")
        self.idp_audience = idp_audience or os.getenv("AUTH0_AUDIENCE")
        self.claims = {
            "user_id": f"{self.idp_audience}/maven_user_id",
            "identities": f"{self.idp_audience}/maven_user_identities",
            "email": f"{self.idp_audience}/maven_email",
            "sub": "sub",
            "sign_up_flow": "sign_up_flow",
        }

    def decode(self, token: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Checks the validity of the JWT"""
        try:
            decoded = jwt.decode(
                token,
                self._get_signing_key(token),
                algorithms=["RS256"],
                audience=self.idp_audience,
                options={
                    "verify_signature": True,
                    "require": ["exp", "iss", "aud"],
                },
                leeway=60,
            )
            return _extract_claims(decoded, self.claims)
        except jwt.exceptions.ExpiredSignatureError as err:
            raise TokenExpiredError(err) from err
        except (
            jwt.exceptions.InvalidTokenError,
            jwt.exceptions.PyJWKClientError,
        ) as err:
            raise TokenValidationError(err) from err

    def get_expires_at(self, token: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            decoded = jwt.decode(
                token,
                self._get_signing_key(token),
                algorithms=["RS256"],
                audience=self.idp_audience,
                options={
                    "verify_signature": True,
                    "require": ["exp", "iss", "aud"],
                },
                leeway=60,
            )
            return decoded.get("exp")
        except jwt.exceptions.ExpiredSignatureError as err:
            raise TokenExpiredError(err) from err
        except (
            jwt.exceptions.InvalidTokenError,
            jwt.exceptions.PyJWKClientError,
        ) as err:
            raise TokenValidationError(err) from err

    @ddtrace.tracer.wrap()
    def _get_signing_key(self, token: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        url = f"https://{self.idp_domain}/.well-known/jwks.json"
        jwk_client = jwt.PyJWKClient(url)
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        return signing_key.key


class DevelopmentDecoder:
    """This should only be used in local testing environments as it does not do JWT signature verification"""

    def __init__(self) -> None:
        self.claims = {
            "user_id": "maven_user_id",
            "identities": "maven_user_identities",
            "email": "maven_email",
            "sub": "sub",
        }

    def decode(self, token: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        decoded = jwt.decode(token, options={"verify_signature": False})
        return _extract_claims(decoded, self.claims)

    def get_expires_at(self, token: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        decoded = jwt.decode(token, options={"verify_signature": False})
        return decoded.get("exp")


def _extract_claims(token_dict: dict, claims: dict):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    extracted = {}
    for claim in claims:
        extracted[claim] = token_dict.get(claims[claim])
    return extracted


class TokenValidationError(Exception):
    ...


class TokenExpiredError(Exception):
    ...
