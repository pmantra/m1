# Error Message
from auth0 import exceptions

REQUEST_TIMEOUT_ERROR = "Request timed out, please try again later"
RATE_LIMIT_ERROR = "Too many requests, try again later"
# Error Code
UNAUTHORIZED_STATUS = 401
CONFLICT_STATUS = 409
RATE_LIMIT_STATUS = 429


class IdentityClientError(Exception):
    """
    This error is the Auth0 server error.
    """

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message


class ClientError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message


class RequestsError(ClientError):
    ...


class RateLimitError(ClientError):
    def __init__(self) -> None:
        super().__init__(code=RATE_LIMIT_STATUS, message=RATE_LIMIT_ERROR)


class DuplicateResourceError(ClientError):
    def __init__(self, message: str) -> None:
        super().__init__(code=CONFLICT_STATUS, message=message)


def process_auth0_err(err: exceptions.Auth0Error) -> None:
    if err.status_code == 409:
        raise DuplicateResourceError(err.message) from err
    elif 400 <= err.status_code < 500:
        raise ClientError(err.status_code, err.message) from err
    else:
        raise IdentityClientError(code=err.status_code, message=err.message) from err
