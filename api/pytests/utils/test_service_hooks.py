from storage.connection import db
from utils.service_hooks import _shutdown_hook


def test_service_shutdown_hook(app):
    with app.app_context():
        engine = db.get_engine(app, "default")
        connectable = db.session.bind

        with connectable.connect() as connection:
            cur_result = connection.execute("SELECT CONNECTION_ID()")
            sql_pid = cur_result.fetchall()[0][0]

            assert sql_pid > 0

        # here it will be something like "... Connections in pool: 1 ..."
        _shutdown_hook(app)
        # now it will be an empty pool
        pool_status = engine.pool.status()
        assert "Connections in pool: 0" in pool_status
