from __future__ import annotations

import pytest
from sqlalchemy import Column, Text

from glidepath import glidepath
from messaging.models.messaging import Message
from storage.connection import db
from tasks.queues import job
from utils.data import JSONAlchemy


def test_respond_with_queries():
    with pytest.raises(AssertionError):
        with glidepath.respond():
            # any queries should cause a failure
            _ = (
                db.session()
                .using_bind("default")
                .execute(
                    "SELECT 1",
                    {},
                )
                .fetchall()
            )


def test_respond_no_queries():
    with glidepath.respond():
        # expect no exception
        pass


def test_guard_commit_boundary_transient(db):
    @glidepath.guard_commit_boundary()
    def test_func():
        _ = Message()

    # we expect to receive an explicit failure exception
    # object was created but not added
    with pytest.raises(pytest.fail.Exception):
        test_func()


def test_guard_commit_boundary_pending(db):
    @glidepath.guard_commit_boundary()
    def test_func():
        m = Message()
        db.session.add(m)

    # we expect to receive an explicit failure exception
    # object was added but not flushed or committed
    with pytest.raises(pytest.fail.Exception):
        test_func()


def test_guard_commit_boundary_persistent(db):
    @glidepath.guard_commit_boundary()
    def test_func():
        m = Message()
        db.session.add(m)
        db.session.flush()

    # we expect to receive an explicit failure exception
    # object was flushed but not committed
    with pytest.raises(pytest.fail.Exception):
        test_func()


def test_guard_commit_boundary_valid(db):
    @glidepath.guard_commit_boundary()
    def test_func():
        m = Message()
        db.session.add(m)
        # note flush is not required before commit
        db.session.commit()

    # expect no failure exception
    # object was committed
    test_func()


def test_guard_commit_boundary_retrieve_then_update(db):
    # put some message in the db
    m = Message()
    db.session.add(m)
    db.session.commit()

    @glidepath.guard_commit_boundary()
    def test_func_no_update():
        existing_msg = db.session.query(Message).filter(Message.id == m.id).one()
        assert existing_msg is not None

    # no exception should be thrown because the msg is not dirty
    test_func_no_update()

    @glidepath.guard_commit_boundary()
    def test_func_update():
        existing_msg = db.session.query(Message).filter(Message.id == m.id).one()
        assert existing_msg is not None

        existing_msg.body = "some new message"

    # expect a failure exception because the msg is dirty
    with pytest.raises(pytest.fail.Exception):
        test_func_update()

    @glidepath.guard_commit_boundary()
    def test_func_update_with_commit_only():
        existing_msg = db.session.query(Message).filter(Message.id == m.id).one()
        assert existing_msg is not None

        existing_msg.body = "some new message"
        db.session.commit()

    # objects loaded are implicitly loaded into the session
    test_func_update_with_commit_only()

    @glidepath.guard_commit_boundary()
    def test_func_update_with_commit_and_add():
        existing_msg = db.session.query(Message).filter(Message.id == m.id).one()
        assert existing_msg is not None

        existing_msg.body = "some new message"
        db.session.add(existing_msg)
        db.session.commit()

    # explicitly adding has no effect
    # this is the same as only calling commit.
    test_func_update_with_commit_and_add()


def test_guard_commit_boundary_on_setter(db):
    class SomeModelA(db.Model):
        __tablename__ = "table_a"
        id = db.Column(db.Integer, primary_key=True)
        json = Column(JSONAlchemy(Text(1000)), default={})

        @property
        def a_prop(self):
            return self.json

        @a_prop.setter
        def a_prop(self, value):
            self.json = {}
            self.json["foo"] = value

    class SomeModelB(db.Model):
        __tablename__ = "table_b"
        id = db.Column(db.Integer, primary_key=True)

        @glidepath.GuardedCommitProperty
        def no_commit_prop(self):
            return self.json

        @no_commit_prop.setter
        def no_commit_prop(self, value):
            a = db.session.query(SomeModelA).first()
            a.a_prop = value
            # NOTE: we have not committed the changes we just made to a. We
            # expect this to cause a test failure

        @glidepath.GuardedCommitProperty
        def with_commit_prop(self):
            return self.json

        @with_commit_prop.setter
        def with_commit_prop(self, value):
            a = db.session.query(SomeModelA).first()
            a.a_prop = value
            # NOTE: an add here is not required because the object was loaded
            # from the DB directly into the session.
            db.session.commit()

    # make the test tables
    db.Model.metadata.create_all(db.session.bind.engine)

    # set up some existing data
    model_a = SomeModelA()
    model_b = SomeModelB()
    db.session.add(model_a)
    db.session.add(model_b)
    db.session.commit()

    fetched_b = db.session.query(SomeModelB).first()
    # we expect to receive an explicit failure exception
    with pytest.raises(pytest.fail.Exception):
        fetched_b.no_commit_prop = "some value"

    # we dont expect a failure exception here because we properly committed the
    # changes
    fetched_b.with_commit_prop = "some value"


def test_guard_commit_boundary_require_mocked_delays(mock_queue):
    @job
    def some_cool_job():
        pass

    @glidepath.guard_commit_boundary()
    def test_func():
        some_cool_job.delay()

    # we do not allow unmocked delays to be called within a guarded commit
    # boundary under test.
    with pytest.raises(pytest.fail.Exception):
        test_func()
