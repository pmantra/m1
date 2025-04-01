from __future__ import annotations

import concurrent.futures

import gevent
import pytest


def test_core_session_binding(given_app, given_db, replica_url):
    # Given

    given_bind_key = "app_replica"
    given_session_proxy = given_db.s_app_replica
    # When
    engine = given_db.get_engine(bind=given_bind_key)
    bound_session = given_session_proxy()
    unbound_session = given_db.session()

    # Then
    # The bound session proxy automatically switches to the target engine
    assert bound_session.bind == engine
    # The target engine is pointing to the correct db
    assert engine.url == replica_url
    # The bound session proxy is using the same underlying session as the unbound
    assert bound_session.session == unbound_session
    # The unbound session is pointing at the default db, not the target db.
    assert unbound_session.bind.url != replica_url


def test_session_management(given_db, given_model, given_table):
    # Given
    # Define an ORM model with the new db.
    # Create a new entry using the ORM
    given_instance = given_model()
    given_db.session.add(given_instance)
    # Commit it so that we can test row-locking.
    given_db.session.commit()
    # When
    # Send an update using the ORM.
    #   This will lock this row.
    given_instance.col = "first"
    given_db.session.flush()
    # Perform a second update using a vanilla table construct
    #   This will deadlock if our session routing isn't defaulting to the correct
    #   bind, because it will create a new connection pool.
    given_db.session.execute(
        given_table.update()
        .where(given_table.c.id == given_instance.id)
        .values(col="second"),
    )
    # Perform a third update using raw SQL
    #   This will deadlock if our session routing isn't defaulting to the correct
    #   bind, because it will again create a new connection pool.
    given_db.session.execute(
        f"UPDATE test_model SET col = 'third' WHERE id = {given_instance.id}"
    )
    table_row = given_db.session.execute(given_table.select()).first()
    raw_sql_row = given_db.session.execute("select * from test_model").first()
    given_db.session.refresh(given_instance)
    # Then
    assert given_instance and table_row and raw_sql_row
    assert (
        (given_instance.id, given_instance.col)
        == (table_row.id, table_row.col)
        == (raw_sql_row.id, raw_sql_row.col)
    )


def test_threaded_concurrency(given_db, given_model, given_app):
    # Given
    given_range = 1_000

    def given_routine(n):
        with given_app.app_context():
            instance = given_model(col=str(n))
            given_db.session.add(instance)
            given_db.session.commit()
            return instance.id

    # When
    with concurrent.futures.ThreadPoolExecutor() as executor:
        ids = [*executor.map(given_routine, range(given_range))]

    assert len(ids) == given_range


@pytest.mark.requires_gevent
def test_gevent_concurrency(given_app, given_db, given_model, given_table):
    # Given
    given_workers = 10
    given_range = 1_000
    given_iterations = 1_000 // given_workers

    def given_routine(n):
        with given_app.app_context():
            instance = given_model(col=str(n))
            given_db.session.add(instance)
            given_db.session.commit()
            return instance.id

    ids = []
    for i in range(given_iterations):
        greenlets = [gevent.spawn(given_routine, i) for i in range(given_workers)]
        ids.extend(gevent.joinall(greenlets))
    assert len(ids) == given_range
