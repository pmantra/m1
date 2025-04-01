#!/usr/bin/env python3
from __future__ import annotations

# Import ddtrace.auto and patch all.
import ddtrace.auto

ddtrace.patch_all()

import dataclasses
import logging
import signal
import typing as t

import flask
import waitress
from structlog import contextvars

import configuration


def serve(app: flask.Flask) -> t.NoReturn:
    logger = logging.getLogger("server")
    config = configuration.get_server_config()
    contextvars.bind_contextvars(server=dataclasses.asdict(config))
    try:
        logger.info("Server booting up.")
        waitress.serve(
            app=app,
            host=config.host,
            port=config.port,
            threads=config.threads,
            backlog=config.request_backlog,
            connection_limit=config.connection_limit,
            channel_timeout=config.channel_timeout,
            cleanup_interval=config.cleanup_interval,
            expose_tracebacks=True,
        )
    except (KeyboardInterrupt, SystemExit) as e:
        logger.info(f"Got signal to shutdown: {e!r}")
    except Exception:
        logger.error("Got an unhandled server error.")
        raise
    finally:
        logger.info("Server exited.")


EXIT_SIGNALS = (signal.SIGINT, signal.SIGTERM)


if __name__ == "__main__":
    # Load in any local env files.
    try:
        import dotenv

        dotenv.load_dotenv(verbose=True)
    except ImportError:
        pass

    # Import the app instance after all the patching to avoid side effects.
    from application import wsgi

    serve(wsgi)
