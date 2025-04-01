import pytest
from sqlalchemy.exc import IntegrityError

from pytests.factories import (
    VirtualEventCategoryFactory,
    VirtualEventCategoryTrackFactory,
)
from storage.connection import db


def test_virtual_event_category_required_fields():
    with pytest.raises(IntegrityError):
        VirtualEventCategoryFactory(name=None)
    db.session.rollback()


def test_virtual_event_category_unique_fields():
    VirtualEventCategoryFactory(name="pregnancy-101")
    with pytest.raises(IntegrityError):
        VirtualEventCategoryFactory(name="pregnancy-101")
    db.session.rollback()


def test_virtual_event_category_track_required_fields():
    cat = VirtualEventCategoryFactory(name="pregnancy-101")

    with pytest.raises(IntegrityError):
        VirtualEventCategoryTrackFactory(category=cat)
    db.session.rollback()

    with pytest.raises(IntegrityError):
        VirtualEventCategoryTrackFactory(track_name="pregnancy")
    db.session.rollback()

    assert VirtualEventCategoryTrackFactory(category=cat, track_name="pregnancy")


def test_virtual_event_category_track_validations():
    cat = VirtualEventCategoryFactory(name="surrogacy-101")
    with pytest.raises(ValueError):
        VirtualEventCategoryTrackFactory(
            category=cat,
            track_name="surrogacy",
            availability_start_week=42,
            availability_end_week=13,
        )
    db.session.rollback()
    assert VirtualEventCategoryTrackFactory(
        category=cat,
        track_name="surrogacy",
        availability_start_week=13,
        availability_end_week=42,
    )
