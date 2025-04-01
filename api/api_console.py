#!/usr/bin/env python3
import os
import sys

import click
import ddtrace

API_DIR = os.path.dirname(__file__)

log = None

json_logs = click.option(
    "--json-logging",
    "-jl",
    is_flag=True,
    help="Use JSON Rendering instead of Key-Value Rendering for log output",
)
enable_trace = click.option(
    "--enable-tracing", "-t", is_flag=True, help="Enable request tracing in log-output."
)


def _init_logging(json_logging: bool, enable_tracing: bool) -> None:
    global log
    if log is None:
        if not json_logging:
            os.environ["DEV_LOGGING"] = "1"
        if not enable_tracing:
            os.environ["DISABLE_TRACING"] = "1"
            ddtrace.tracer.enabled = False

        from utils.log import logger

        log = logger(__name__)


@click.group()
@json_logs
@enable_trace
def db(json_logging: bool = False, enable_tracing: bool = False) -> None:
    """Manage the DB of the API with these functions"""
    _init_logging(json_logging, enable_tracing)


@db.command("init", help="Create databases if they don't exist yet.")
def init_db() -> None:
    from storage.dev import setup_dbs

    setup_dbs()


@db.command("destroy")
@click.confirmation_option(prompt="Are you sure you want to drop the db? (!)")
def destroy_db() -> None:
    """DANGEROUS! Destroy the DB, all of it. FOREVER..."""
    from app import create_app
    from storage.connection import db as _db

    app = create_app()
    with app.app_context():
        _db.drop_all(bind="__all__")


@db.command(
    "ready",
    add_help_option=True,
    help="Attempt to connect to the database in the given period, exiting with success if the database is up.",
)
@click.option(
    "--interval", type=int, default=3, help="How many seconds to wait between checks."
)
@click.option(
    "--timeout",
    type=int,
    default=600,
    help="How many seconds we will try to connect to the database for.",
)
def ready(interval, timeout):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    from datetime import datetime, timedelta
    from time import sleep

    from sqlalchemy.exc import OperationalError

    from app import create_app
    from storage.connection import db as _db

    with create_app().app_context():
        deadline = datetime.utcnow() + timedelta(seconds=timeout)
        while True:
            try:
                _db.session.execute("SELECT 1;")
                print("Database ready!")
                sys.exit(0)
            except OperationalError:
                if datetime.utcnow() > deadline:
                    print(
                        f"Database readiness check exceeded deadline of {timeout} seconds."
                    )
                    sys.exit(1)
                else:
                    print(f"Checking readiness in {interval} seconds...")
                    sleep(interval)


@db.command(
    "migrate",
    add_help_option=True,
    help="Migrates default database to HEAD revision.",
)
def migrate() -> None:
    import pathlib

    from alembic import command
    from alembic.config import Config

    DIR = pathlib.Path(__file__).resolve()

    alembic_ini_file = DIR.parent / "alembic.ini"
    default_cfg = Config(alembic_ini_file)

    command.upgrade(default_cfg, "head")


@db.command(
    "seed",
    add_help_option=True,
    help="Seeds the database with data-admin fixtures.",
)
def db_seed() -> None:
    from app import create_app
    from utils.fixtures import restore_fixtures

    with create_app().app_context():
        restore_fixtures()


@click.group()
@json_logs
@enable_trace
def dev(json_logging: bool = False, enable_tracing: bool = False) -> None:
    """Useful dev helpers"""
    _init_logging(json_logging, enable_tracing)


@dev.command("shell")
def shell_launcher() -> None:
    """Launch a shell with some helpful stuff loaded."""
    from utils import shell

    shell.Shell().embed()


@dev.command("server")
def dev_server() -> None:
    """Run the flask dev server"""

    os.environ["DEBUG"] = "True"
    from app import create_app

    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


@dev.command("export")
def export() -> None:
    """Export database configuration data.

    $ kubectl exec api-shell-xxx-yyy dev export > api/schemas/io/snapshot.py

    Make sure not to pass -t to kubectl exec as it will make click pollute our snapshot with color escape sequences.
    """
    # Avoid writing logs into the generated file.
    import logging

    from app import create_app

    logging.disable(logging.CRITICAL)
    app = create_app()
    with app.app_context():
        from schemas.io import export

        export()


@dev.command("snapshot-size")
def snapshot_size() -> None:
    """Estimate the size of exported configuration data.

    Can be useful for correctness analysis of export and
    restore especially when size is compared across snapshots.

    This will not reflect how much memory snapshots will take in memory,
    nor how much memory they will occupy in the database when restored.
    """
    from app import create_app

    app = create_app()
    with app.app_context():
        import pickle

        from schemas.io import Fixture, snapshot

        snapshot_attrs = set(dir(snapshot))
        ff = sorted(
            (f for f in Fixture if f.name in snapshot_attrs), key=lambda f: f.value
        )
        for f in ff:
            size = len(pickle.dumps(getattr(snapshot, f.name)))
            print(f"{f.name}: {size} bytes")


if __name__ == "__main__":
    sys.exit(dev())
