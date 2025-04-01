from __future__ import annotations

import contextlib
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

import maven.feature_flags as feature_flags
from sqlalchemy import event
from sqlalchemy.orm import Session

from storage.connection import db
from utils.log import logger

if TYPE_CHECKING:
    from typing import Callable, Iterable

log = logger(__name__)


GLIDEPATH_UNCOMMITTED_ORM_OBJECTS_FAILURE_WRAPPER = """Glidepath discovered uncommitted ORM objects!
The following objects will be lost when leaving the `glidepath.guard_commit_boundary()` scope.
More info: docs/code/glidepath/glidepath.md

created but not added: {created_but_not_added}
added but not flushed: {added_but_not_flushed}
not committed:         {flushed_but_not_committed_objects}

{failure_messages}
"""

GLIDEPATH_UNCOMMITTED_ORM_OBJECTS_FAILURE_MESSAGE = """
ORM object:           {identity_key}
property name:        {property_name}
committed value       {committed_value}
current object value: {current_obj_value}
"""


@dataclass
class GlidepathCommitFailureContext:
    """
    Context about a per-field commit omission on an ORM object.
    """

    identity_key: str
    property_name: str
    committed_value: str
    current_obj_value: str


def on_enter_guarded_commit_boundary() -> list[Callable]:
    """
    Called when entering a `guard_commit_boundary` scope.
    It will return a list of callables that will executed on commit boundary
    scope exit. Ensure any cleanup hooks are added to this list.
    """

    return []


def on_exit_guarded_commit_boundary(
    cleanup_hooks: list[Callable],
) -> None:
    """
    Called when exiting a `guard_commit_boundary` scope.
    It will call all provided cleanup hooks.
    """
    return None


def session_object_evaluation(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
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
        log.error(reason, exc_info=True)


def should_rollback_exiting_commit_boundary() -> bool:
    """
    Returns True if we should always rollback the session when exiting a guarded
    commit boundary. The goal should be to drive this to True 100% of the time.
    For further explanation and reasoning please see:
    docs/code/glidepath/glidepath.md
    """
    # TODO: move this to a flag group when the MR is merged
    # waiting on the flag group MR to be merged ...
    # https://gitlab.com/maven-clinic/maven/maven/-/merge_requests/10063
    return feature_flags.bool_variation(
        "release-glidepath-rollback-on-exit",
        # default to not processing inbound messages with the v2 pipeline
        default=False,
    )


def get_all_dirty_session_objects() -> set:
    """
    Returns a set of all ORM objects that have been modified but not committed.
    """
    all_dirty_objects = set()

    # review every object in the session
    for obj in db.session.identity_map.all_states():
        # if the object has been modified, add it to the set
        all_dirty_objects.add(obj) if obj.modified else None

    return all_dirty_objects


class GuardedCommitProperty(property):
    """
    This provides a convenient decorator for ensuring db interaction hygiene is
    maintained within the scope of a class property.

    Example usage:
    class SomeModel(db.Model):
        __tablename__ = "sups_coo_table"
        id = db.Column(db.Integer, primary_key=True)

        @glidepath.GuardedCommitProperty
        def cool_prop(self):
            return self.value

        @b_prop.setter
        def b_prop(self, value):
            # any activities you want to ensure are persisted

    """

    def __set__(self, obj, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with guard_commit_boundary():
            super().__set__(obj, value)


@contextlib.contextmanager
def guard_commit_boundary(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Wrap a scope of actions that define a bounded set of work. Examples
    include:
    - the code between the input parse and the response serialization in an API
      handler
    - a job (task) function (decorated as @job...) that is run in a worker
    - a function that has multiple evaluation steps and model changes that
      should be either all committed or all rolled back (transactional scope)
    """

    # storage for detected activity
    created_but_not_added = set()
    added_but_not_flushed = set()
    flushed_but_not_committed_objects = set()

    # any instantiation of an ORM object will be captured and added to the
    # created_but_not_added set. This is used to detect objects that have been
    # created but not added to the session.
    @event.listens_for(db.Model, "init", propagate=True)
    def _on_create(target, args, kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        nonlocal created_but_not_added
        created_but_not_added.add(target)

    # an orm object has been created but not sent to the db. it does not
    # contain any db assigned fields (like id). the obj is still in a
    # transaction and if not committed will be lost.
    @event.listens_for(Session, "transient_to_pending")
    def _on_transient_to_pending(session, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        nonlocal created_but_not_added
        created_but_not_added.discard(obj)
        added_but_not_flushed.add(obj)

    # an orm object has been written to the and and now contains all db default
    # assigned fields (like id). the obj is still in a transaction and if not
    # committed will be lost.
    @event.listens_for(Session, "pending_to_persistent")
    def _on_pending_to_persistent(session, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        nonlocal added_but_not_flushed
        nonlocal flushed_but_not_committed_objects
        added_but_not_flushed.discard(obj)
        flushed_but_not_committed_objects.add(obj)

    # a new transaction has been started. due to the behavior of the shared
    # session object we may assume that there are no objects in the session.
    @event.listens_for(Session, "after_begin")
    def _on_after_begin(session, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        nonlocal added_but_not_flushed
        nonlocal flushed_but_not_committed_objects
        added_but_not_flushed = set()
        flushed_but_not_committed_objects = set()

    @event.listens_for(Session, "after_commit")
    def _on_after_commit(session, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        nonlocal added_but_not_flushed
        nonlocal flushed_but_not_committed_objects
        for obj in session:
            added_but_not_flushed.discard(obj)
            flushed_but_not_committed_objects.discard(obj)

    # a transaction has been rolled back. all objects in the session have been
    # lost, including those that had been written to the db (flushed) and
    # assigned defaults, but not committed.
    @event.listens_for(Session, "after_soft_rollback")
    def _on_after_soft_rollback(session, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        nonlocal added_but_not_flushed
        nonlocal flushed_but_not_committed_objects
        added_but_not_flushed = set()
        flushed_but_not_committed_objects = set()

    # hook that is called when entering the scope.
    cleanup_hooks = on_enter_guarded_commit_boundary()

    yield  # execute the code under guard

    issued_discovered: list[GlidepathCommitFailureContext] = []
    for obj in get_all_dirty_session_objects():
        for property_name, committed_value in obj.committed_state.items():
            current_obj_value = obj.attrs[property_name].value
            # find the difference between the committed value and the current
            # there may be multiple for a single ORM object. create an issue
            # entry for each.
            if committed_value != current_obj_value:
                issued_discovered.append(
                    GlidepathCommitFailureContext(
                        identity_key=f"{obj.identity_key}",
                        property_name=property_name,
                        committed_value=committed_value,
                        current_obj_value=current_obj_value,
                    )
                )

    # During application run, session_object_evaluation is a noop. During testing, we hook into
    # the `examine_session` function to detect dirty ORM objects that have not been
    # committed and raise an error. This ensures that tests wont pass unless the
    # persistance of all model changes have been explicitly managed.
    session_object_evaluation(
        issued_discovered=issued_discovered,
        created_but_not_added=created_but_not_added,
        added_but_not_flushed=added_but_not_flushed,
        flushed_but_not_committed_objects=flushed_but_not_committed_objects,
    )

    # hook that is called when exiting the scope.
    on_exit_guarded_commit_boundary(cleanup_hooks=cleanup_hooks)

    # rollback() is done in the exit path to ensure ORM caching behavior cannot
    # introduce unexpected query results in db.session call made following this
    # execution scope.
    # A common mistake is to forget to call commit() after making a series of
    # changes to a model instance or an explicit mutating query. Queries later
    # in the call flow that reference the modified instance will access the
    # cached state and not what is in the db. This can lead to db.session.query
    # commands returning resources that are not actually persisted in the db.
    if should_rollback_exiting_commit_boundary():
        db.session.rollback()


@contextlib.contextmanager
def respond():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Use in an API handler to wrap the serialization of response data.
    """
    yield
