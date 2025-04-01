from __future__ import annotations

import contextlib
from dataclasses import asdict
from typing import Callable, Iterable
from unittest import mock

import pytest

from glidepath.glidepath import (
    GLIDEPATH_UNCOMMITTED_ORM_OBJECTS_FAILURE_MESSAGE,
    GLIDEPATH_UNCOMMITTED_ORM_OBJECTS_FAILURE_WRAPPER,
    GlidepathCommitFailureContext,
    get_all_dirty_session_objects,
)
from pytests.db_util import enable_db_performance_warnings
from storage.connection import db
from utils.log import logger

log = logger(__name__)


GLIDEPATH_UNMOCKED_DELAY_FOUND = """Glidepath captured a nested attempt to enqueue an unmocked job: {job_name}
During testing, an execution scope that contains a call to `.delay()` will attempt
to execute that task in-process. If that job fails (and has retries available) no exception
will be raised to the executor and the test will pass without any error signal.
This leaves a large space for incorrect assumptions to be made about the
behavior of the code under test. 
- Job execution must be tested separately. 
- Mocking the job will allow this test to proceed.
\nMore info: docs/code/glidepath/glidepath.md
"""


def glidepath_query_limiter(
    db,
    query_limit: int = 1,
):
    """
    Forces the code within the yield scope to make no more than `query_limit`
    calls to the db.

    """

    @contextlib.contextmanager
    def _wrapper():
        with enable_db_performance_warnings(
            database=db,
            failure_threshold=query_limit,
        ):
            yield

    return _wrapper


def glidepath_session_object_evaluation(
    issued_discovered: Iterable[GlidepathCommitFailureContext] | None = None,
    created_but_not_added: set | None = None,
    added_but_not_flushed: set | None = None,
    flushed_but_not_committed_objects: set | None = None,
):
    """
    Hook called just before an explicit rollback() giving us an opportunity to
    examine the db session and raise an error if there are dirty objects that
    have not been committed.
    We must not rely on some upper scope to "hopefully" call commit().
    """

    # after scope exit we assert that all ORM objects added to any transaction
    # in the yielded scope have been committed. During application operation,
    # there is NO guarantee that an upstream scope will call commit() on the
    # session. This enforces transactional hygiene and ensures we avoid
    # unexpected runtime behavior.
    try:
        # all object modifications must be committed
        assert not issued_discovered
        # All objects that have been created must be added to the session. If
        # the code path under test proactively creates an object then
        # conditionally decides to add it or not, it could lead to unexpected
        # behavior at runtime. To avoid this we require that all objects are
        # added to the session after their creation.
        assert not created_but_not_added
        assert not added_but_not_flushed
        assert not flushed_but_not_committed_objects
    except AssertionError:
        failure_messages = "\n".join(
            [
                GLIDEPATH_UNCOMMITTED_ORM_OBJECTS_FAILURE_MESSAGE.format(**asdict(obj))
                for obj in issued_discovered or []
            ]
        )
        reason = GLIDEPATH_UNCOMMITTED_ORM_OBJECTS_FAILURE_WRAPPER.format(
            failure_messages=failure_messages,
            created_but_not_added=created_but_not_added,
            added_but_not_flushed=added_but_not_flushed,
            flushed_but_not_committed_objects=flushed_but_not_committed_objects,
        )
        # explicitly force the test to fail
        pytest.fail(reason=reason)


def glidepath_on_enter_guarded_commit_boundary() -> list[Callable]:
    """
    Called when entering a `guard_commit_boundary` scope.
    """
    cleanup_hooks = []

    # force test failure
    def block_unmocked_job(job_fn, *args, **kwargs):
        pytest.fail(
            reason=GLIDEPATH_UNMOCKED_DELAY_FOUND.format(job_name=job_fn.__name__)
        )

    # the position of this import is important. It must be within execution
    # scope. If hoisted, it executes during module load which is prior to the
    # session level mock patch occurring in api/conftest.py. This results in as
    # patching the wrong object and leaving us without a path to override the
    # enqueue method.
    from tasks.queues import _queues as job_queues

    for _, q in job_queues.items():
        if hasattr(q.enqueue, "side_effect"):
            q.enqueue.side_effect = block_unmocked_job
        else:
            q.enqueue = mock.Mock()
            q.enqueue.side_effect = block_unmocked_job

    # Replaces the call to db.session.commit(). This is used to trigger a flush
    # of the objects in the session. All objects in the session have now been
    # persisted to the db and will be available on subsequent queries.
    def fake_commit():
        for obj in get_all_dirty_session_objects():
            for property_name in obj.committed_state.keys():
                obj.committed_state[property_name] = obj.attrs[property_name].value

        # write the data to the DB (simulate the commit)
        db.session.flush()
        # emit the after_commit event that would normally occur after a commit
        db.session.session_factory().dispatch.after_commit(db.session)

    # There is an explicit modification to the commit behavior added in
    # api/conftest.py that sets commit to flush. To allow for tests to accurately
    # mirror prod expectations we reset the behavior to its original state. This
    # happens on entering a `glidepath.guard_commit_boundary` and is restored to
    # the modification when exiting. This allows for all existing tests to
    # continue to function and provide the additional guarantees to only the
    # glidepath decorated application scopes.
    cached_flush = getattr(db.session, "_flush")  # noqa: B009
    setattr(db.session, "commit", fake_commit)  # noqa: B010
    setattr(db.session, "flush", cached_flush)  # noqa: B010

    return cleanup_hooks


def glidepath_on_exit_guarded_commit_boundary(
    cleanup_hooks: list[Callable],
) -> None:
    """
    Called when exiting a `guard_commit_boundary` scope.
    It will call all provided cleanup hooks.
    """
    for hook in cleanup_hooks:
        try:
            hook()
        except Exception as e:
            log.exception("Exception during hook cleanup", exception=e)

    # Restore the db session.commit behavior that was applied in
    # api/conftest.py. It is imperative to restore on
    # `glidepath.guard_commit_boundary` exit so that all other tests continue to
    # operate as expected.
    cached_flush = getattr(db.session, "_flush")  # noqa: B009
    # reset to the original test runner commit and flush behavior
    setattr(db.session, "commit", cached_flush)  # noqa: B010
    setattr(db.session, "flush", cached_flush)  # noqa: B010

    return None
