import pathlib

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

MIGRATIONS = pathlib.Path(__file__).parent.parent / "schemas" / "migrations"


# https://blog.jerrycodes.com/multiple-heads-in-alembic-migrations/
def test_only_single_head_revision_in_migrations():
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    script = ScriptDirectory.from_config(config)

    # This will raise if there are multiple heads
    script.get_current_head()

    # to show heads: script.get_heads()


def test_get_source_head():
    from schemas.migrations.alembic_utils import get_source_head

    curr_head = get_source_head()
    assert curr_head is not None


def test_start_monitoring_loop_exceptions():
    from threading import Event

    from schemas.migrations.alembic_utils import get_source_head, start_monitoring_loop

    exit_event = Event()
    db_name = "default"
    curr_head = get_source_head()

    with pytest.raises(AssertionError):
        start_monitoring_loop(
            exiting_event=exit_event,
            db_name=db_name,
            source_head=curr_head,
            db_head=curr_head,
            wakeup_interval_in_seconds=-1,
        )

    with pytest.raises(AssertionError):
        start_monitoring_loop(
            exiting_event=exit_event,
            db_name=db_name,
            source_head=curr_head,
            db_head=curr_head,
            max_wait_interval_in_seconds=1,
            wakeup_interval_in_seconds=1.0,
        )


def test_start_monitoring_loop_event():
    import time
    from threading import Event

    from schemas.migrations.alembic_utils import get_source_head, start_monitoring_loop

    exit_event = Event()
    db_name = "default"
    curr_head = get_source_head()

    start_monitoring_loop(
        exiting_event=exit_event,
        db_name=db_name,
        source_head=curr_head,
        db_head=curr_head,
        max_wait_interval_in_seconds=0.5,
        wakeup_interval_in_seconds=0.3,
    )

    exit_event.set()
    max_wait_count = 5
    current_wait_count = 0
    # wait for the event to be clear by the monitoring thread
    while exit_event.is_set() and current_wait_count < max_wait_count:
        current_wait_count = current_wait_count + 1
        time.sleep(1)

    assert exit_event.is_set() is False


@pytest.mark.parametrize(argnames="db_name", argvalues=["default"])
def test_start_monitoring_healing(app, db_name):
    from threading import Event

    import sqlalchemy

    from schemas.migrations.alembic_utils import get_source_head, start_monitoring_loop
    from storage.connection import db

    exit_event = Event()
    curr_head = get_source_head()

    # mimic env.py logic
    with app.app_context():
        connectable = db.session.bind

        with connectable.connect() as connection:
            cur_result = connection.execute("SELECT CONNECTION_ID()")
            sql_pid = cur_result.fetchall()[0][0]

            assert sql_pid > 0

            start_monitoring_loop(
                exiting_event=exit_event,
                db_name=db_name,
                source_head=curr_head,
                db_head=curr_head,
                sql_pid=sql_pid,
                max_wait_interval_in_seconds=1,
                wakeup_interval_in_seconds=0.2,
            )

            with pytest.raises(Exception) as exc_info:
                # simulate long running queries
                connection.execute("SELECT SLEEP(3)")

            assert exc_info.type is sqlalchemy.exc.OperationalError
            assert (
                exc_info.value.args[0]
                == "(pymysql.err.OperationalError) (2013, 'Lost connection to MySQL server during query')"
            )

    # timeout and healing scenario
    assert exit_event.is_set() is False
