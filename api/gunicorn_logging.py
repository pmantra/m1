import os

from utils import log


class GunicornLogger:
    """Adapted from:
    - https://github.com/benoitc/gunicorn/blob/ab9c8301cb9ae573ba597154ddeea16f0326fc15/gunicorn/glogging.py
    - https://gist.github.com/airhorns/c2d34b2c823541fc0b32e5c853aab7e7

    """

    def __init__(self, cfg):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._error_logger = log.logger("gunicorn.error", server=dict(pid=os.getgid()))
        self._access_logger = log.logger("gunicorn.access")
        self.cfg = cfg

    def critical(self, msg, *args, **kwargs) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        kwargs.update(server=dict(pid=os.getgid()))
        self._error_logger.error(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        kwargs.update(server=dict(pid=os.getgid()))
        self._error_logger.error(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        kwargs.update(server=dict(pid=os.getgid()))
        self._error_logger.warning(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        kwargs.update(server=dict(pid=os.getgid()))
        self._error_logger.info(msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        kwargs.update(server=dict(pid=os.getgid()))
        self._error_logger.debug(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        kwargs.update(server=dict(pid=os.getgid()))
        self._error_logger.exception(msg, *args, **kwargs)

    def log(self, lvl, msg, *args, **kwargs) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        kwargs.update(server=dict(pid=os.getgid()))
        self._error_logger.log(lvl, msg, *args, **kwargs)

    def access(self, resp, req, environ, request_time) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        status = resp.status
        if isinstance(status, str):
            status = status.split(None, 1)[0]

        # Grab request headers for tracking in logs.
        request_headers = req
        if hasattr(req, "headers"):
            request_headers = req.headers

        if hasattr(request_headers, "items"):
            request_headers = request_headers.items()

        response_headers = resp.headers
        if hasattr(response_headers, "items"):
            response_headers = response_headers.items()

        request_headers_dict = {
            k.lower(): v for k, v in request_headers if k.lower().startswith("x")
        }
        response_headers_dict = {
            k.lower(): v for k, v in response_headers if k.lower().startswith("x")
        }
        # Extract important correlation data
        info_dict = dict(
            http=dict(
                method=environ["REQUEST_METHOD"],
                protocol=environ["SERVER_PROTOCOL"],
                host=environ.get("REMOTE_ADDR", "-"),
                path=environ.get("PATH_INFO", "-"),
                status=status,
                response=dict(
                    length=getattr(resp, "length", None), **response_headers_dict
                ),
                referer=environ.get("HTTP_REFERER", "-"),
                user_agent=environ.get("HTTP_USER_AGENT", "-"),
                **request_headers_dict,
            ),
            server=dict(
                pid=os.getgid(),
                software=environ.get("SERVER_SOFTWARE"),
                time=dict(
                    seconds=request_time.seconds,
                    microseconds=request_time.microseconds,
                ),
            ),
        )
        self._access_logger.debug(
            "request",
            **info_dict,
        )

    def reopen_files(self) -> None:
        pass  # we don't support files

    def close_on_exec(self) -> None:
        pass  # we don't support files
