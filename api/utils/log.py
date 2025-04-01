from __future__ import annotations

import logging
import logging.config
import os
from enum import Enum
from typing import Callable, List, Tuple

import ddtrace
import structlog
from maven.observability import logs
from sqlalchemy import log as sqlalchemy_log

import configuration
from utils import gcp


class LogLevel(Enum):
    INFO = 1
    WARNING = 2
    ERROR = 3


def configure(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    *,
    project: str = None,  # type: ignore[assignment] # Incompatible default for argument "project" (default has type "None", argument has type "str")
    json: bool = None,  # type: ignore[assignment] # Incompatible default for argument "json" (default has type "None", argument has type "bool")
    level: str | int = None,  # type: ignore[assignment] # Incompatible default for argument "level" (default has type "None", argument has type "Union[str, int]")
    **context,
):
    """Set up structlog with formatting and context providers for your app."""
    project = project or gcp.safe_get_project_id()
    if json is None:
        json = os.environ.get("DEV_LOGGING") not in ("1", "true", "True")
    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO")
    shared, structured, renderer = _get_processors(json)
    formatting = {
        "()": structlog.stdlib.ProcessorFormatter,
        "processor": renderer,
        "foreign_pre_chain": shared,
    }
    level = logging.getLevelName(level.upper()) if isinstance(level, str) else level
    # we specify force because ddtrace messes with the root handler in a way
    # that screws up our logging, so we're force-resetting the root handler to
    # be what we want
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": True,
            "formatters": {"default": formatting},
            "handlers": {
                "default": {
                    "level": level,
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                }
            },
            "loggers": {
                "": {  # type: ignore[typeddict-unknown-key] # Extra key "force" for TypedDict "_LoggerConfiguration"
                    "handlers": ["default"],
                    "level": level,
                    "propagate": True,
                    "force": True,
                }
            },
        }
    )
    structlog.configure(
        processors=shared + structured,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        # `json` is a proxy for whether this is a deployment or dev/test
        cache_logger_on_first_use=json,
    )
    sqla = configuration.get_common_config().sqlalchemy
    # Patch to avoid duplicate logging
    sqlalchemy_log._add_default_handler = lambda lg: lg.addHandler(  # type: ignore[attr-defined] # Module has no attribute "_add_default_handler"
        logging.NullHandler()
    )
    if sqla.echo is False:
        logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    logging.getLogger("ddtrace").setLevel(level + 10)
    structlog.contextvars.bind_contextvars(**context, project=project)


def _get_processors(json: bool) -> Tuple[List, List, Callable]:

    shared = [
        logs.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionPrettyPrinter(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        add_correlation_ids,
    ]
    structured = [structlog.stdlib.PositionalArgumentsFormatter()]

    if json:
        # `json=True` is sort of a proxy for whether we're in a context that will
        # be reporting to GCP. In those cases, we want these processors so that our
        # logging plays nicely with our monitoring.
        shared.append(patch_alternate_keys)
        renderer = structlog.processors.JSONRenderer()
    else:
        # Otherwise, we're probably testing or running in a dev environment.
        # Make it easy on the eyes.
        renderer = structlog.dev.ConsoleRenderer()

    # Add the formatter wrapper as the last callee in the processors for structlog.
    structured.append(structlog.stdlib.ProcessorFormatter.wrap_for_formatter)
    return shared, structured, renderer


def patch_alternate_keys(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    """Add alternates to common keys for log sinks."""

    for target, source in _ALTERNATES:
        if source not in event_dict or target in event_dict:
            continue
        event_dict[target] = event_dict[source]
    return event_dict


def add_correlation_ids(logger, name: str, event_dict: dict) -> dict:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    # get correlation ids from current tracer context and set them in the event dict.
    event_dict["dd"] = ddtrace.tracer.get_log_correlation_context()
    return event_dict


_ALTERNATES = (("severity", "level"), ("message", "event"))
_DEFAULT_SEVERITY = "info"


def logger(name: str, **initial_values) -> structlog.stdlib.BoundLogger:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    if structlog.is_configured() is False:
        configure()
    return structlog.stdlib.get_logger(name, **initial_values)


def generate_user_trace_log(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    log: structlog.stdlib.BoundLogger,
    log_level: LogLevel,
    user_id: str,
    log_message: str,
    **other_values,
):

    if log_level == LogLevel.ERROR:
        log.error(log_message, user_id=user_id, **other_values)
    elif log_level == LogLevel.WARNING:
        log.warning(log_message, user_id=user_id, **other_values)
    else:
        log.info(log_message, user_id=user_id, **other_values)
