from storage.connection import db
from utils.log import logger

log = logger(__name__)


def register_worker_shutdown_hook(app):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    import atexit

    atexit.register(_shutdown_hook, app)


def _shutdown_hook(app):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        if app.config["SQLALCHEMY_BINDS"]:
            for k in app.config["SQLALCHEMY_BINDS"]:
                log.debug(f"[shutdown_hook] about to close connections for bind {k}")
                engine = db.get_engine(app, k)
                engine.dispose()
    except Exception as e:
        log.error(f"[shutdown_hook] exception when closing DB connections: {e}")
    log.info(
        "maven app instance is shutting down, the associated DB connections are closed"
    )
