import time
from datetime import datetime
from os import getenv
from secrets import compare_digest

import jwt

from utils.log import logger

log = logger(__name__)


class RotatableToken(object):
    """RotatableToken manages a plaintext bearer token that can be rotated using a set of environment variables.

    A rotatable token is constituted of a primary token, an optional secondary token, and an optional secondary token
    expiration timestamp. These values are represented by environment variables following a naming convention; given a
    rotatable token name of 'FOO', the values will be respectively read from environment variables FOO_PRIMARY,
    FOO_SECONDARY, and FOO_SECONDARY_EXPIRES_AT.

    Example:
        foo_token = RotatableToken('FOO')
        if foo_token.check_token('some value from a client'):
            return 'the underlying resource'
        else:
            return 'not authorized!'

    Tokens can also be used for encoding/decoding data using JSON Web Tokens. The primary token is always used for encoding.

    Example:
        token = RotatableToken('Foo')
        result = token.encode({'blah': 'things'})
        decoded_result = token.decode(result)

    """

    def __init__(self, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.name = name
        self.primary = self._get_token("PRIMARY")
        self.secondary = self._get_token("SECONDARY")
        self.secondary_expires_at = self.secondary and self._get_secondary_expires_at()

    def _get_token(self, suffix):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return getenv(f"{self.name}_{suffix}")

    def _get_secondary_expires_at(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        key = f"{self.name}_SECONDARY_EXPIRES_AT"
        value = getenv(key)
        if value is None:
            log.warn("%s was not provided; secondary token will not expire.", key)
            return

        try:
            ts = int(value)
            ts = datetime.utcfromtimestamp(ts)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "datetime", variable has type "int")
            return ts
        except Exception as e:
            log.warn(
                "%s could not be parsed; secondary token will not expire: %s.", key, e
            )

    @property
    def _primary_not_valid(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.primary is None

    @property
    def _secondary_not_valid(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.secondary is None:
            return True

        if self.secondary_expires_at is None:
            return False

        if self.secondary_expires_at < datetime.utcnow():
            log.warn('Secondary token "%s" has expired.', self.name)
            self.secondary = None  # Short circuit secondary expiration.
            return True

        return False

    def check_token(self, token):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """check_token validates a provided bearer token against a primary or expiring secondary token.

        Args:
            token: a token provided by the client to be checked.

        Returns:
            True if the token is valid, or False if it is not.

        Raises:
            TokenUnavailableError: If the token has not been defined by the environment.
        """
        if self._primary_not_valid:
            raise TokenUnavailableError(self.name)

        if compare_digest(self.primary, token):
            return True

        if self._secondary_not_valid:
            return False

        return compare_digest(self.secondary, token)

    def encode(self, data, exp=600):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Encodes data into a JWT using the rotatable token.

        Args:
            data: dict of data that you wish to encode.

        Kwargs:
            exp: timeout in seconds, defaults to 10 minutes.

        Returns:
            The JWT as a str.

        Raises:
            TokenUnavailableError: If the token has not been defined by the environment.
        """
        if self._primary_not_valid:
            raise TokenUnavailableError(self.name)
        now = int(time.time())
        return jwt.encode({**{"exp": now + exp}, **data}, self.primary, "HS256")

    def decode(self, token):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Decodes the given JWT using the rotatable token.

        Args:
            token: str JWT to decode

        Returns:
            The decoded data as a dict, or None if the token could not be decoded

        Raises:
            TokenUnavailableError: If the token has not been defined by the environment
        """
        if self._primary_not_valid:
            raise TokenUnavailableError(self.name)
        payload = self._jwt_decode(self.primary, token)
        if payload is None:
            if self._secondary_not_valid:
                return
            payload = self._jwt_decode(self.secondary, token)
            if payload is None:
                return

        payload.pop("exp")
        payload.pop("iat", None)
        return payload

    def _jwt_decode(self, rotatable_token, jwt_token):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return jwt.decode(
                jwt=jwt_token,
                key=rotatable_token,
                algorithms=["HS256"],
                options={"verify_signature": True, "verify_exp": True},
            )

        except (jwt.exceptions.InvalidTokenError, jwt.exceptions.InvalidKeyError) as e:
            log.warning("Error decoding token", exception_message=str(e))


class TokenUnavailableError(ValueError):
    def __init__(self, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(f"Token {name!r} has not been provided by the environment.")


BRAZE_CONNECTED_CONTENT_TOKEN = RotatableToken("BRAZE_CONNECTED_CONTENT_TOKEN")
BRAZE_BULK_MESSAGING_TOKEN = BRAZE_CONNECTED_CONTENT_TOKEN
BRAZE_CONNECTED_EVENT_TOKEN = RotatableToken("BRAZE_CONNECTED_EVENT_TOKEN")
BRAZE_ATTACHMENT_TOKEN = RotatableToken("BRAZE_ATTACHMENT_TOKEN")
SECURITY_SIGNING_TOKEN = RotatableToken("SECURITY_SIGNING_TOKEN")
ZENDESK_WEBHOOK_TOKEN = RotatableToken("ZENDESK_WEBHOOK_TOKEN")
