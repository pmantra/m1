from models.profiles import AgreementNames
from storage.connection import db
from utils.migrations.backfill_agreement_acceptance import backfill_in_batches


def test_skip_non_null(factories, default_user):
    # When
    aa = factories.AgreementAcceptanceFactory.create(user=default_user, accepted=False)

    # Then
    backfill_in_batches()
    db.session.expire_all()

    # Test that
    assert aa.accepted is False


def test_set_accepted_value(factories, default_user):
    # When
    aa = factories.AgreementAcceptanceFactory.create(user=default_user, accepted=None)

    # Then
    backfill_in_batches()
    db.session.expire_all()

    # Test that
    assert aa.accepted is True


def test_set_in_batches(factories, default_user):
    # When
    aa_1 = factories.AgreementAcceptanceFactory.create(
        user=default_user,
        agreement=factories.AgreementFactory.create(name=AgreementNames.TERMS_OF_USE),
        accepted=None,
    )
    aa_2 = factories.AgreementAcceptanceFactory.create(
        user=default_user,
        agreement=factories.AgreementFactory.create(name=AgreementNames.PRIVACY_POLICY),
        accepted=None,
    )
    aa_3 = factories.AgreementAcceptanceFactory.create(
        user=default_user,
        agreement=factories.AgreementFactory.create(name=AgreementNames.GINA),
        accepted=None,
    )

    # Then
    backfill_in_batches(batch_size=2)
    db.session.expire_all()

    # Test that
    assert aa_1.accepted is True
    assert aa_2.accepted is True
    assert aa_3.accepted is True
