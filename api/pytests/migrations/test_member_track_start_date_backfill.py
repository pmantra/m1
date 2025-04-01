import datetime

from storage.connection import db
from utils.migrations.backfill_member_track_start_date import backfill_in_batches


def test_skip_non_null(factories):
    # When
    tomorrow = datetime.datetime.utcnow().date() + datetime.timedelta(days=1)
    mt = factories.MemberTrackFactory.create(start_date=tomorrow)

    # Then
    backfill_in_batches()
    db.session.expire_all()

    # Test that
    assert mt.start_date == tomorrow


def test_set_start_date(factories):
    # When
    today = datetime.datetime.utcnow()
    yesterday = today - datetime.timedelta(days=1)

    mt = factories.MemberTrackFactory.create(created_at=yesterday)
    mt.start_date = None

    # Then
    backfill_in_batches()
    db.session.expire_all()

    # Test that
    assert mt.start_date == yesterday.date()


def test_set_in_batches(factories):
    # When
    today = datetime.datetime.utcnow()
    yesterday = today - datetime.timedelta(days=1)
    vorgestern = today - datetime.timedelta(days=2)

    mt_1 = factories.MemberTrackFactory.create(created_at=today)
    mt_1.start_date = None

    mt_2 = factories.MemberTrackFactory.create(created_at=yesterday)
    mt_2.start_date = None

    mt_3 = factories.MemberTrackFactory.create(created_at=vorgestern)
    mt_3.start_date = None

    # Then
    backfill_in_batches(batch_size=2)
    db.session.expire_all()

    # Test that
    assert mt_1.start_date == today.date()
    assert mt_2.start_date == yesterday.date()
    assert mt_3.start_date == vorgestern.date()
