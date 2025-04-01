import time
from functools import wraps

from utils.log import logger

log = logger(__name__)
MAX_RETRY = 3


def retry_action(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    exceptions, tries=MAX_RETRY, delay=1, backoff=2, exception_message: str = ""
):
    """Retry calling the decorated function using an exponential backoff.

    http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    :param exceptions: the exception to check. Maybe a tuple of exceptions to check
    :type exceptions: Exception or a tuple of Exceptions
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay each retry
    :type backoff: int
    :param exception_message: the exception message substring of the exceptions to check.
                              Default is not checking exception message
    :type exception_message: str
    """

    def decorator(f):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        @wraps(f)
        def f_retry(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except exceptions as e:
                    if (
                        not exception_message
                        or exception_message.lower() in str(e).lower()
                    ):
                        log.warn(f"Error: {e} Retrying in {mdelay} seconds...")
                        time.sleep(mdelay)
                        mtries -= 1
                        mdelay *= backoff
                    else:
                        raise
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return decorator
