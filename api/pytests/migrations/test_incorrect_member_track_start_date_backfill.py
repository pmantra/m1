import datetime

from storage.connection import db
from utils.migrations.backfill_incorrect_member_track_start_date import (
    backfill_in_batches,
)


def test_skip_matching(factories):
    # When
    yesterday = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    mt = factories.MemberTrackFactory.create(
        start_date=yesterday.date(), created_at=yesterday
    )

    # Then
    backfill_in_batches()
    db.session.expire_all()

    # Test that
    assert mt.start_date == yesterday.date()


def test_update_start_date(factories):
    # When
    today = datetime.datetime.utcnow()
    yesterday = today - datetime.timedelta(days=1)

    mt = factories.MemberTrackFactory.create(
        created_at=yesterday, start_date=today.date()
    )

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
    vorvorgestern = today - datetime.timedelta(days=3)

    mt_1 = factories.MemberTrackFactory.create(
        created_at=yesterday, start_date=today.date()
    )

    mt_2 = factories.MemberTrackFactory.create(
        created_at=vorgestern, start_date=today.date()
    )

    mt_3 = factories.MemberTrackFactory.create(
        created_at=vorvorgestern, start_date=today.date()
    )

    # Then
    backfill_in_batches(batch_size=2)
    db.session.expire_all()

    # Test that
    assert mt_1.start_date == yesterday.date()
    assert mt_2.start_date == vorgestern.date()
    assert mt_3.start_date == vorvorgestern.date()
