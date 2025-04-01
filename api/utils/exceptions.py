import functools
import os
import re
import traceback
from logging import ERROR, FATAL

from flask import g, has_request_context, request
from google.cloud import error_reporting

from utils.error_reporting import MAVEN_IGNORE_EXCEPTIONS
from utils.log import logger

VERSION = os.environ.get("VERSION", "unset")

log = logger(__name__)


class DeleteUserActionableError(ValueError):
    """DeleteUserActionableError is raised for conditions that the care coordinator can do something about."""

    pass


class ProgramLifecycleError(ValueError):
    status_code = 400
    display_message = (
        "Something went wrong. Please contact support@mavenclinic.com for help."
    )
    log_level = ERROR


class StaleDataError(ValueError):
    status_code = 409
    display_message = "This data is stale. Please refresh the browser."
    log_level = ERROR


class UserInputValidationError(ValueError):
    status_code = 422
    display_message = "User input failed validations."
    log_level = ERROR


class RelationalConflictError(ProgramLifecycleError):
    status_code = 500


class UserRequiredError(ProgramLifecycleError):
    status_code = 500
    log_level = FATAL

    def __init__(self, lifecycle):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(f"{lifecycle} requires a user.")


class EmployeeRequiredError(ProgramLifecycleError):
    status_code = 500
    log_level = FATAL

    def __init__(self, lifecycle):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(f"{lifecycle} requires an employee.")


class ProgramRequiredError(ProgramLifecycleError):
    status_code = 500
    log_level = FATAL

    def __init__(self, lifecycle):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(f"{lifecycle} requires a program.")


class IntendedModuleRequiredError(ProgramLifecycleError):
    status_code = 500
    log_level = FATAL

    def __init__(self, lifecycle):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(f"{lifecycle} requires an intended module.")


class ModuleNotAvailableError(ProgramLifecycleError):
    display_message = (
        "It looks like the program you selected isn't available through your employer "
        "at this time. Please reach out to your Care Advocate."
    )


class ModuleNotAllowedError(ModuleNotAvailableError):
    def __init__(self, lifecycle):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(
            "{} not allowed to initiate program for intended module for employee.".format(
                lifecycle
            )
        )


class CurrentPhaseRequiredError(ProgramLifecycleError):
    status_code = 500

    def __init__(self, lifecycle):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(f"{lifecycle} requires program to have a current phase.")


class ActiveTransitionRequiredError(ProgramLifecycleError):
    def __init__(self, lifecycle):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(f"{lifecycle} requires a program with an active transition.")


class TransitionDashboardRequiredError(ProgramLifecycleError):
    status_code = 500
    log_level = FATAL

    def __init__(self, lifecycle, transition):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        msg = "{} requires transition {} dashboard to define at least one dashboard version."
        super().__init__(msg.format(lifecycle, transition))


class ActiveOrganizationRequiredError(ProgramLifecycleError):
    def __init__(self, lifecycle, organization):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        msg = "{} cannot create an enrollment for an inactive organization {}."
        super().__init__(msg.format(lifecycle, organization))


class ActiveEmployeeRequiredError(ProgramLifecycleError):
    def __init__(self, lifecycle):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(
            "{} cannot create an enrollment for a deleted organization employee.".format(
                lifecycle
            )
        )


class ModuleConfigurationError(ProgramLifecycleError):
    """Raised when the user-agnostic state of the module is invalid for the desired operation."""

    pass


class ModuleUserStateError(ProgramLifecycleError):
    """Raised when the user-specific state of the module is invalid for the desired operation."""

    pass


class ScheduledEndOutOfRangeError(ModuleUserStateError):
    pass


class DueDateRequiredError(ModuleUserStateError):
    display_message = (
        "Due date not found. Please contact support@mavenclinic.com for help."
    )


class LastChildBirthdayRequiredError(ModuleUserStateError):
    display_message = (
        "Baby DOB not found. Please contact support@mavenclinic.com for help."
    )


class InvalidPhaseTransitionError(ProgramLifecycleError):
    status_code = 500


class AutoTransitionEnrollmentNotAllowedError(ProgramLifecycleError):
    status_code = 500
    log_level = FATAL

    def __init__(self, lifecycle):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        msg = "{} not allowed to auto transition across an enrollment boundary."
        super().__init__(msg.format(lifecycle))


class DraftUpdateAttemptException(StaleDataError):
    def __init__(self, lifecycle: str) -> None:
        msg = f"{lifecycle}. Please refresh browser or restart your app."
        super().__init__(msg)


def send_stackdriver_exception(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    A decorator to send exceptions to stackdriver, e.g. for use on functions
    called directly from a cron task.

    DEPRECATED: use log_exception instead (below)
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return func(*args, **kwargs)
        except Exception:
            log.exception("Exception while running function...")
            if any(isinstance(t, t) for t in MAVEN_IGNORE_EXCEPTIONS):
                log.debug("Ignorable exception, skip stackdriver reporting.")
                return
            client = error_reporting.Client(service="python")
            client.report_exception()
            raise

    return wrapper


# Useful breakdown on the pieces of a URL and their ordering:
#   https://skorks.com/2010/05/what-every-developer-should-know-about-urls/
_KEY_FILTER_REGEX = re.compile(
    # Search for any key which contains these words
    r"\w*("
    # The `=` indicates this is a key
    r"(?<=name=)|"
    r"(?<=email=)|"
    r"(?<=birth=)|"
    r"(?<=number=)"
    # The value-match terminates at the next parameter or fragment, if there is one.
    r")([^?&;#]+)+"
)


def _obfuscate_parameters(url: str, *, sub: str = "***") -> str:
    return _KEY_FILTER_REGEX.sub(sub, url)


def _flask_context():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if has_request_context():
        context = error_reporting.build_flask_context(request)
        context.url = _obfuscate_parameters(context.url)
        return context.__dict__
    return None


def _error_reporting_fields(service: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    stat_doc = g.request_stat_doc if hasattr(g, "request_stat_doc") else {}
    user_id = stat_doc.get("user_id", None)
    version = VERSION
    if len(version) > 8:
        version = version[:8]

    # See: https://cloud.google.com/error-reporting/docs/formatting-error-messages
    return {
        "serviceContext": {"service": service, "version": version},
        "@type": "type.googleapis.com/google.devtools.clouderrorreporting.v1beta1.ReportedErrorEvent",
        "context": {"httpRequest": _flask_context(), "user": user_id},
    }


def log_exception(e: Exception, service: str = "api") -> None:
    """
    Sends an exception to stackdriver by properly formatting a log message.
    Arguments:
        e:       The exception.
        service: The name of the service to be logged with the error. Defaults to 'api'
    """
    tb_exception = traceback.TracebackException.from_exception(e)
    log.error("".join(tb_exception.format()), **_error_reporting_fields(service))


def log_exc_info(exc_info, service: str = "api"):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    """
    Sends an exception to stackdriver by properly formatting a log message.
    Arguments:
        exc_info: An exception information tuple, such as provided by sys.exc_info().
        service: The name of the service to be logged with the error. Defaults to 'api'
    """
    log.error(
        "".join(traceback.format_exception(*exc_info)),
        **_error_reporting_fields(service),
    )


def log_exception_message(message: str, service: str = "api") -> None:
    """
    Sends a message to stackdriver by properly formatting a log message.
    Arguments:
        message: The message to send.
        service: The name of the service to be logged with the error. Defaults to 'api'
    """
    if os.environ.get("TESTING"):
        log.warning(f"Error: {message}")
        return
    stack = [
        "Traceback (most recent call last):\n",
        *traceback.format_stack(),
        f"Error: {message}",
    ]
    full_error_message = "".join(stack)
    log.error(full_error_message, **_error_reporting_fields(service))
