from __future__ import annotations

import dataclasses
import json
from collections import defaultdict
from typing import Any, DefaultDict, List, Mapping

import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.util
from sqlalchemy import desc
from sqlalchemy.sql import Select

from direct_payment.billing import models
from direct_payment.billing.repository.common import UUID, UUIDEncoder
from storage.repository import base

TEXT_BLOB_BYTES_SIZE = 65535


class BillProcessingRecordRepository(base.BaseRepository[models.BillProcessingRecord]):
    model = models.BillProcessingRecord

    @staticmethod
    def instance_to_values(instance: models.BillProcessingRecord) -> dict:
        instance_dict = dataclasses.asdict(instance)
        # faux-json field for old mysql
        json_str = json.dumps(instance_dict["body"], cls=UUIDEncoder)
        if len(json_str.encode("utf-8")) > TEXT_BLOB_BYTES_SIZE:
            raise ValueError(
                "MYSQL will truncate processing_record_bodies of this size."
            )
        instance_dict["body"] = json_str
        return instance_dict

    @classmethod
    def deserialize(
        cls, row: Mapping[str, Any] | None
    ) -> models.BillProcessingRecord | None:
        if row is None:
            return  # type: ignore[return-value] # Return value expected
        # faux-json field for old mysql
        row_data = dict(row)
        row_data["body"] = json.loads(row_data["body"])
        return cls.model(**row_data)

    @staticmethod
    def table_columns() -> tuple[sqlalchemy.Column, ...]:
        return (
            sa.Column("processing_record_type", sa.String(100), nullable=False),
            sa.Column("body", sa.Text, nullable=False),
            sa.Column("bill_id", sa.BigInteger, nullable=False),
            # TODO: note bill_status is a str version of an enum column on the main bill
            # This is to prevent having to update multiple tables at a time and as it's purely a record keeping column.
            sa.Column("bill_status", sa.Text, nullable=False),
            # sa.Column("bill_payment_method_label", sa.Text, nullable=True) PAY-4284
            sa.Column("transaction_id", UUID(allow_none=True), nullable=True),
        )

    # Overwrite this due to lack of modified_at column
    @classmethod
    def identity_columns(cls) -> tuple[sqlalchemy.Column, ...]:
        return (
            sqlalchemy.Column("id", sqlalchemy.BigInteger, primary_key=True),
            sqlalchemy.Column(
                "created_at",
                sqlalchemy.TIMESTAMP,
                nullable=False,
                server_default=sqlalchemy.FetchedValue(),
            ),
        )

    def get_bill_processing_attempt_count(self, bill: models.Bill) -> int:
        where = sa.and_(
            self.table.c.bill_id == bill.id,
            self.table.c.processing_record_type == "payment_gateway_request",
        )
        columns = (sqlalchemy.func.count(self.table.c.id),)
        query = sqlalchemy.select(columns=columns, whereclause=where)
        result = self.session.scalar(query)
        return result

    def get_bill_processing_records(
        self, bill_ids: List[int]
    ) -> list[models.BillProcessingRecord]:
        where = sa.and_(self.table.c.bill_id.in_(bill_ids))
        result = self.execute_select(where=where)
        to_return = [self.deserialize(row) for row in result.fetchall()]
        return to_return  # type: ignore[return-value] # Incompatible return value type (got "List[Optional[BillProcessingRecord]]", expected "List[BillProcessingRecord]")

    def get_latest_bill_processing_record_if_paid(
        self, bill_ids: List[int]
    ) -> models.BillProcessingRecord | None:
        """
        Returns the last created bill processing record - which is in Paid state and is the last record for a bill.
        None if not found
        :param bill_ids: Iterable of bill ids
        :type bill_ids: Iterable of ints
        :return: last created bill processing record - which is in Paid state and is the last record for a bill.
        :rtype:BillProcessingRecord or None
        """
        return self.get_latest_row_with_specified_statuses(
            bill_ids, [models.BillStatus.PAID]
        )

    def get_latest_row_with_specified_statuses(
        self, bill_ids: List[int], statuses: List[models.BillStatus]
    ) -> models.BillProcessingRecord | None:
        """
        Returns the last created bill processing record - in any of the input states and is the last record for a bill.
        None if not found
        :param bill_ids: Bill ids in scope/
        :type bill_ids: List of ints
        :param statuses: Any of these bill statuses is acceptable as the head record on a bill
        :type statuses: list of bill statuses
        :return:last created bill processing record - in one of the input state and is the last record for a bill.
        :rtype: BillProcessingRecord or None
        """
        if not bill_ids:
            return None
        main_select = self._create_sql_for_latest_row_with_specified_statuses(
            bill_ids, statuses
        )
        result = self.session.execute(main_select).first()
        to_return = None
        if result:
            res_dict = dict(result)
            del res_dict["rhs_bill_id"]
            del res_dict["max_id"]
            to_return = self.deserialize(res_dict)
        return to_return

    def get_latest_records_with_specified_statuses_for_bill_ids(
        self, bill_ids: List[int], statuses: List[models.BillStatus]
    ) -> dict[int, models.BillProcessingRecord]:
        """
        Returns a dict of the bill ids to the last bill processing record if the record is one of the specified statuses.
        Bills that don't have a match will not have entries in the dict.
        :param bill_ids: Bill ids in scope
        :type bill_ids: List of ints
        :param statuses: Any of these bill statuses is acceptable as the head record on a bill
        :type statuses: list of bill statuses. If empty will return an empty list
        :return: a dict of the bill ids to the last bill processing record
        :rtype: dict[int, models.BillProcessingRecord]
        """
        to_return = {}
        if bill_ids:
            main_select = self._create_sql_for_latest_row_with_specified_statuses(
                bill_ids, statuses
            )
            results = self.session.execute(main_select).fetchall()
            for result in results:
                res_dict = dict(result)
                del res_dict["rhs_bill_id"]
                del res_dict["max_id"]
                bpr = self.deserialize(res_dict)
                to_return[bpr.bill_id] = bpr  # type: ignore[union-attr] # Item "None" of "Optional[BillProcessingRecord]" has no attribute "bill_id"
        return to_return  # type: ignore[return-value] # Incompatible return value type (got "Dict[Union[int, Any], Optional[BillProcessingRecord]]", expected "Dict[int, BillProcessingRecord]")

    def filter_bill_ids_for_money_movement(self, bill_ids: List[int]) -> List[int]:
        """
        Returns a list of bill ids if it has a bpr that is PAID or REFUNDED and has
        a transaction id reflecting money movement.
        Bills that don't have a match will not have ids in the list.
        :param bill_ids: Bill ids in scope
        :type bill_ids: List of ints
        :return: a list of the bill ids with money movement
        :rtype: List of ints
        """
        result_ids = None
        if bill_ids:
            main_select = self._create_sql_for_bills_with_money_movement(bill_ids)
            result = self.session.execute(main_select).fetchall()
            result_ids = [r[0] for r in result]
        return result_ids  # type: ignore[return-value] # Incompatible return value type (got "Optional[List[Any]]", expected "List[int]")

    def _create_sql_for_latest_row_with_specified_statuses(
        self, bill_ids: List[int], statuses: List[models.BillStatus]
    ) -> Select:
        status_list = [sa.literal_column(f"'{status.value}'") for status in statuses]
        table = self.table
        main_table = self.table  # table.alias('main_bpr')
        paid_bpr = sa.select(
            columns=[
                table.c.bill_id.label("rhs_bill_id"),
                sa.func.max(table.c.id).label("max_id"),
            ],
            group_by=table.c.bill_id,
        ).alias("paid_bpr")
        main_select = (
            main_table.join(
                paid_bpr,
                onclause=(
                    (main_table.c.bill_id == paid_bpr.c.rhs_bill_id)
                    & (main_table.c.id == paid_bpr.c.max_id)
                    & (main_table.c.bill_status.in_(status_list))
                    & (main_table.c.bill_id.in_(bill_ids))
                ),
            )
            .select()
            .order_by(desc(main_table.c.id))
        )
        return main_select

    def _create_sql_for_bills_with_money_movement(self, bill_ids: List[int]) -> Select:
        status_list = [
            sa.literal_column(f"'{status.value}'")
            for status in [models.BillStatus.PAID, models.BillStatus.REFUNDED]
        ]
        table = self.table
        where_money_movement = sa.and_(
            self.table.c.bill_status.in_(status_list),
            self.table.c.transaction_id.isnot(None),
        )
        paid_bpr_bill_ids = sa.select(
            columns=[
                table.c.bill_id.label("bill_id"),
            ],
            whereclause=sa.and_(
                self.table.c.bill_id.in_(bill_ids), where_money_movement
            ),
            group_by=table.c.bill_id,
        ).distinct()
        return paid_bpr_bill_ids

    def get_bill_ids_from_transaction_id(self, transaction_id: UUID) -> List[int]:
        """
        Given a transaction id - pull all the associated bill id(s). Does not support query by NONE transaction id.
        :param transaction_id: payment gateway transaction id
        :type transaction_id: UUID
        :return: list of bill ids
        :rtype: List[int]
        """
        results = (
            self.session.query(self.table.c.bill_id)
            .filter(self.table.c.transaction_id == transaction_id)
            .distinct()
            .all()
        )
        to_return = [res[0] for res in results]
        return to_return

    def get_all_records_with_specified_statuses_for_bill_ids(
        self, bill_ids: List[int], statuses: List[models.BillStatus] = None  # type: ignore[assignment] # Incompatible default for argument "statuses" (default has type "None", argument has type "List[BillStatus]")
    ) -> defaultdict[int, list[models.BillProcessingRecord]]:
        """
        :param bill_ids: Input bill ids - if empty or none, nothing is done.
        :param statuses: Optional bill statuses to filter bprs.
        :return: Dict of bill_ids to lists of matching bprs if any. No guarantees of ordering.
        """
        to_return: DefaultDict[int, List[models.BillProcessingRecord]] = defaultdict(
            list
        )
        if bill_ids:
            where_clauses = [self.table.c.bill_id.in_(bill_ids)]
            if statuses:
                where_clauses.append(
                    self.table.c.bill_status.in_([s.value for s in statuses])
                )
            res = self.execute_select(where=sa.and_(*where_clauses)).fetchall()
            for row in res:
                to_return[row.bill_id].append(self.deserialize(row))  # type: ignore[arg-type] # Argument 1 to "append" of "list" has incompatible type "Optional[BillProcessingRecord]"; expected "BillProcessingRecord"
        return to_return
