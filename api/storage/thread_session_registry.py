from flask_sqlalchemy import SignallingSession
from werkzeug.local import LocalStack, release_local

from common import stats
from utils.log import logger

log = logger(__name__)


class ThreadSessionRegistry:
    """A :class:`.ThreadSessionRegistry` that uses a ``werkzeug.local.LocalStack()``
    variable for storage.

    """

    def __init__(self) -> None:
        self.registry = LocalStack()

    def add(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # use SignallingSession to avoid circular reference
        assert isinstance(obj, SignallingSession)
        self.registry.push(obj)

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.registry.top

    def remove(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        sess = self.registry.top
        while sess is not None:
            self.registry.pop()
            try:
                sess.close()
            except AttributeError:
                pass
            except AssertionError as e:
                log.warning(f"exception in session remove logic: {e}")
                stats.increment(
                    metric_name="mono.session.tear_down.exception",
                    pod_name=stats.PodNames.CORE_SERVICES,
                    tags=["resource:default", "type:assertion"],
                )
                pass
            sess = self.registry.top
        release_local(self.registry)
