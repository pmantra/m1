from logging.config import fileConfig

from alembic import context
from maven import feature_flags

import os
import threading

API_DIR = os.path.dirname(__file__)

import configuration
from common import stats
from storage.connection import db

from utils import log

logger = log.logger(__name__)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name, disable_existing_loggers=False)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    conf = configuration.get_api_config()
    context.configure(
        url=conf.common.sqlalchemy.databases.default_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    run_migrations(context)


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    from app import create_app

    feature_flags.initialize()
    app = create_app()
    with app.app_context():
        db_name = config.get_main_option("db_name")
        if db_name == "audit":
            logger.info(f"Indicated {db_name} database. Not running migrations.")
            return
        else:
            connectable = db.get_engine()

        with connectable.connect() as connection:
            # setting "transaction_per_migration=True" may not be helpful since we run once per MR
            context.configure(connection=connection, target_metadata=target_metadata)

            with_migration = False
            migration_wrapup_event = threading.Event()
            try:
                from schemas.migrations.alembic_utils import (
                    get_source_head,
                    start_monitoring_loop,
                )

                # get the server side PID for the current connection
                cur_result = connection.execute("SELECT CONNECTION_ID()")
                sql_pid = cur_result.fetchall()[0][0]

                db_head = context.get_context().get_current_revision()
                source_head = get_source_head(db_name=db_name)

                logger.info(
                    f"======== Database: {connection.engine.url.database} "
                    f"- Starting migration for db {db_name}, sql_pid: {sql_pid}, "
                    f"db_revision: {db_head}, source_version: {source_head}"
                )
                with_migration = db_head != source_head

                # setup to wake up every 5 seconds for now, will adjust based on metrics
                start_monitoring_loop(
                    exiting_event=migration_wrapup_event,
                    db_name=db_name,
                    source_head=source_head,
                    db_head=db_head,
                    sql_pid=sql_pid,
                    wakeup_interval_in_seconds=5,
                )
            except Exception as e:
                logger.error(
                    f"Exception when running additional logic for for db {db_name} before running migrations: {e}"
                )

            with stats.timed(
                metric_name="mono.migrations.duration",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"db_name:{db_name}", f"with_migration:{with_migration}"],
            ):
                run_migrations(context, exiting_event=migration_wrapup_event)
                logger.info(
                    f"======== Database: {connection.engine.url.database} "
                    f"- DB {db_name} current db revision: {context.get_context().get_current_revision()}"
                )


def run_migrations(cxt, exiting_event: threading.Event = None):
    with cxt.begin_transaction():
        cxt.run_migrations()

    if exiting_event:
        # if passed in, wake up everybody waiting for the signal
        exiting_event.set()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
