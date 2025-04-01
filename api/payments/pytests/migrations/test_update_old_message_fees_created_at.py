from datetime import date, datetime
from unittest import mock

import pytest
from dateutil.relativedelta import relativedelta

from appointments.models.payments import FeeAccountingEntry, FeeAccountingEntryTypes
from payments.migrations.update_old_message_fees_created_at import (
    update_old_message_fees_created_at,
    update_old_message_fees_created_at_chunk,
)
from storage.connection import db


class TestUpdateOldMessageFeesCreatedAt:
    @pytest.fixture()
    def old_message_1(self, factories):
        user = factories.DefaultUserFactory.create()
        prac = factories.PractitionerProfileFactory.create(user=user)
        created_at = datetime.utcnow() - relativedelta(days=14)
        message = factories.MessageFactory.create(
            created_at=created_at,
            user_id=prac.user.id,
        )
        fee = factories.FeeAccountingEntryFactory(
            created_at=datetime.utcnow(),
            message=message,
            type=FeeAccountingEntryTypes.MESSAGE,
        )
        return {"message": message, "fee": fee}

    @pytest.fixture()
    def old_message_2(self, factories):
        user = factories.DefaultUserFactory.create()
        prac = factories.PractitionerProfileFactory.create(user=user)
        created_at = datetime.utcnow() - relativedelta(days=17)
        message = factories.MessageFactory.create(
            created_at=created_at,
            user_id=prac.user.id,
        )
        fee = factories.FeeAccountingEntryFactory(
            created_at=datetime.utcnow(),
            message=message,
            type=FeeAccountingEntryTypes.MESSAGE,
        )
        return {"message": message, "fee": fee}

    @pytest.fixture()
    def old_message_3(self, factories):
        user = factories.DefaultUserFactory.create()
        prac = factories.PractitionerProfileFactory.create(user=user)
        created_at = datetime.utcnow() - relativedelta(days=21)
        message = factories.MessageFactory.create(
            created_at=created_at,
            user_id=prac.user.id,
        )
        fee = factories.FeeAccountingEntryFactory(
            created_at=datetime.utcnow(),
            message=message,
            type=FeeAccountingEntryTypes.MESSAGE,
        )
        return {"message": message, "fee": fee}

    @pytest.fixture()
    def new_message_1(self, factories):
        user = factories.DefaultUserFactory.create()
        prac = factories.PractitionerProfileFactory.create(user=user)
        created_at = datetime.utcnow() - relativedelta(days=1)
        message = factories.MessageFactory.create(
            created_at=created_at,
            user_id=prac.user.id,
        )
        fee = factories.FeeAccountingEntryFactory(
            created_at=datetime.utcnow(),
            message=message,
            type=FeeAccountingEntryTypes.MESSAGE,
        )
        return {"message": message, "fee": fee}

    @pytest.fixture()
    def ancient_message_1(self, factories):
        user = factories.DefaultUserFactory.create()
        prac = factories.PractitionerProfileFactory.create(user=user)
        created_at = datetime.utcnow() - relativedelta(days=60)
        message = factories.MessageFactory.create(
            created_at=created_at,
            user_id=prac.user.id,
        )
        fee = factories.FeeAccountingEntryFactory(
            created_at=datetime.utcnow(),
            message=message,
            type=FeeAccountingEntryTypes.MESSAGE,
        )
        return {"message": message, "fee": fee}

    def test_update_old_message_fees_created_at__no_messages_found(
        self, factories, ancient_message_1, new_message_1
    ):
        # Given - we only have messages outside the range
        msg_start_date = (datetime.utcnow() - relativedelta(days=21)).date()
        msg_end_date = (datetime.utcnow() - relativedelta(days=7)).date()
        fae_date_created = date.today()

        # When we run our function
        fees_count = update_old_message_fees_created_at(
            msg_start_date,
            msg_end_date,
            fae_date_created,
        )

        # Than - No records found
        assert fees_count == 0

    def test_update_old_message_fees_created_at__one_message_found(
        self, factories, ancient_message_1, new_message_1, old_message_1
    ):
        # Given - we only have messages outside the range
        msg_start_date = (datetime.utcnow() - relativedelta(days=21)).date()
        msg_end_date = (datetime.utcnow() - relativedelta(days=7)).date()
        fae_date_created = date.today()

        # When we run our function
        fees_count = update_old_message_fees_created_at(
            msg_start_date,
            msg_end_date,
            fae_date_created,
        )

        # Than - One record found (two not found)
        assert fees_count == 1

    def test_update_old_message_fees_created_at__two_messages_found(
        self,
        factories,
        old_message_1,
        old_message_2,
    ):
        # Given - we only have messages outside the range
        msg_start_date = (datetime.utcnow() - relativedelta(days=21)).date()
        msg_end_date = (datetime.utcnow() - relativedelta(days=7)).date()
        fae_date_created = date.today()

        # When we run our function
        fees_count = update_old_message_fees_created_at(
            msg_start_date,
            msg_end_date,
            fae_date_created,
        )

        # Than - Two records found
        assert fees_count == 2

    @mock.patch(
        "payments.migrations.update_old_message_fees_created_at.update_old_message_fees_created_at_chunk"
    )
    def test_update_old_message_fees_created_at__two_chunks(
        self, mock_chunk, old_message_1, old_message_2, old_message_3
    ):
        # Given - we only have messages outside the range
        msg_start_date = (datetime.utcnow() - relativedelta(days=21)).date()
        msg_end_date = (datetime.utcnow() - relativedelta(days=7)).date()
        fae_date_created = date.today()
        chunk_size = 2

        # When we run our function
        fees_count = update_old_message_fees_created_at(
            msg_start_date, msg_end_date, fae_date_created, chunk_size
        )

        # Than - Three records found, two chunks
        assert fees_count == 3
        assert mock_chunk.delay.call_count == 2

    def test_update_old_message_fees_created_at_chunk__verify_database(
        self, old_message_1, old_message_2, old_message_3
    ):  # old_message_1 has created_at 14 days ago, 17, 21 respectively for the other two.

        # When we try updating fees created today for messages created_at between 21 and 7 days ago
        update_old_message_fees_created_at_chunk(
            chunk=[old_message_1["fee"], old_message_2["fee"], old_message_3["fee"]],
        )
        # The, I expect the 3 messages' fees created_at to be the same as their message.created_at

        # Message/Fee 1
        fee_1 = db.session.query(FeeAccountingEntry).get(old_message_1["fee"].id)
        fee_1_created_at = fee_1.created_at.strftime("%Y-%m-%d")
        message_1_created_at = old_message_1["message"].created_at.strftime("%Y-%m-%d")
        assert fee_1_created_at == message_1_created_at

        # Message/Fee 2
        fee_2 = db.session.query(FeeAccountingEntry).get(old_message_2["fee"].id)
        fee_2_created_at = fee_2.created_at.strftime("%Y-%m-%d")
        message_2_created_at = old_message_2["message"].created_at.strftime("%Y-%m-%d")
        assert fee_2_created_at == message_2_created_at
        # Message/Fee 3
        fee_3 = db.session.query(FeeAccountingEntry).get(old_message_3["fee"].id)
        fee_3_created_at = fee_3.created_at.strftime("%Y-%m-%d")
        message_3_created_at = old_message_3["message"].created_at.strftime("%Y-%m-%d")
        assert fee_3_created_at == message_3_created_at
