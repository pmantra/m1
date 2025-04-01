from factory.alchemy import SQLAlchemyModelFactory

from appointments.models.payments import PaymentAccountingEntry
from conftest import BaseMeta


class PaymentAccountingEntryFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = PaymentAccountingEntry
