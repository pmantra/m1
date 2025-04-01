from __future__ import annotations

import functools

import ddtrace.ext
import sqlalchemy.orm

from appointments.models.payments import PaymentAccountingEntry
from appointments.utils import query_utils
from mpractice.error import QueryNotFoundError
from mpractice.models.appointment import TransactionInfo
from storage.repository.base import BaseRepository

__all__ = ("TransactionRepository",)

trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class TransactionRepository(BaseRepository[TransactionInfo]):  # type: ignore[type-var] # Type argument "TransactionInfo" of "BaseRepository" must be a subtype of "Instance"
    model = TransactionInfo

    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        is_in_uow: bool = False,
    ):
        super().__init__(session=session, is_in_uow=is_in_uow)
        queries = query_utils.load_queries_from_file(
            "mpractice/repository/queries/transaction.sql"
        )
        if len(queries) == 0:
            raise QueryNotFoundError()
        self.get_appointment_transaction_info_query = queries[0]

    def get_transaction_info_by_appointment_id(
        self, appointment_id: int
    ) -> TransactionInfo | None:
        row = self.session.execute(
            self.get_appointment_transaction_info_query,
            {"appointment_id": appointment_id},
        ).first()
        if row is None:
            return None
        return TransactionInfo(**row)

    @classmethod
    @functools.lru_cache(maxsize=1)
    def make_table(cls) -> sqlalchemy.Table:
        return PaymentAccountingEntry.__table__

    @classmethod
    @functools.lru_cache(maxsize=1)
    def table_columns(cls) -> tuple[sqlalchemy.sql.ColumnElement, ...]:  # type: ignore[override] # Signature of "table_columns" incompatible with supertype "BaseRepository"
        return ()
