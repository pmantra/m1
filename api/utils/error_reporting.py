from werkzeug.exceptions import (
    BadRequest,
    Conflict,
    Forbidden,
    MethodNotAllowed,
    NotFound,
    RequestEntityTooLarge,
    SecurityError,
    Unauthorized,
)

MAVEN_IGNORE_EXCEPTIONS = (
    Forbidden,
    Unauthorized,
    SecurityError,
    Conflict,
    BadRequest,
    MethodNotAllowed,
    NotFound,
    RequestEntityTooLarge,
)
