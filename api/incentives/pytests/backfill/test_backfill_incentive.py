from unittest.mock import mock_open, patch

from incentives.models.incentive import Incentive
from incentives.utils.backfill.backfill_incentive import IncentiveBackfill
from storage.connection import db


def test_backfill_incentive__success(factories):
    # Given a fake CSV file
    data = [
        "type,name,amount,vendor,design_asset,active",
        "Gift card,$25 Amazon gift card,25,Amazon,Amazon gift card,TRUE",
        "Welcome box,Maven welcome box,,Maven,Welcome box,TRUE",
    ]
    fake_csv = "\n".join(data)

    # When
    with patch("builtins.open", mock_open(read_data=fake_csv)):
        errors = IncentiveBackfill.backfill_incentive("fake_file_path.csv")
    db.session.expire_all()

    # Then
    incentive_1 = (
        db.session.query(Incentive)
        .filter_by(
            type="GIFT_CARD",
            name="$25 Amazon gift card",
            amount=25,
            vendor="Amazon",
            design_asset="AMAZON_GIFT_CARD",
            active=True,
        )
        .first()
    )
    incentive_2 = (
        db.session.query(Incentive)
        .filter_by(
            type="WELCOME_BOX",
            name="Maven welcome box",
            vendor="Maven",
            design_asset="WELCOME_BOX",
            active=True,
        )
        .first()
    )

    assert incentive_1
    assert incentive_2
    assert not errors


def test_backfill_incentive__errors(factories):
    # Given a fake CSV file
    data = [
        "type,name,amount,vendor,design_asset,active",
        "GC,$25 Amazon gift card,25,Amazon,Gift card,TRUE",
        "Welcome box,Maven welcome box,,Maven,,TRUE",
    ]
    fake_csv = "\n".join(data)

    # When
    with patch("builtins.open", mock_open(read_data=fake_csv)):
        errors = IncentiveBackfill.backfill_incentive("fake_file_path.csv")
    db.session.expire_all()

    # Then assert errors are as expected (including in different orders)
    assert set(errors).issubset(
        [
            "{'type': ['Invalid incentive_type'], 'design_asset': ['Invalid design_asset']} - NAME: $25 Amazon gift card",
            "{'design_asset': ['Invalid design_asset'], 'type': ['Invalid incentive_type']} - NAME: $25 Amazon gift card",
            "{'design_asset': ['Invalid design_asset']} - NAME: Maven welcome box",
        ]
    )
