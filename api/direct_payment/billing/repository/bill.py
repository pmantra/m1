from __future__ import annotations

import dataclasses
import uuid
from datetime import date, datetime
from typing import Any, Iterable, Mapping, Optional

import ddtrace
import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.util

from direct_payment.billing import models
from direct_payment.billing.models import (
    BillErrorTypes,
    BillStatus,
    CardFunding,
    PaymentMethodType,
    PayorType,
)
from direct_payment.billing.repository.common import UUID
from storage.repository import base
from utils.log import logger

log = logger(__name__)

trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class BillRepository(base.BaseRepository[models.Bill]):  # type: ignore[type-var] # Type argument "Bill" of "BaseRepository" must be a subtype of "Instance"
    model = models.Bill

    @staticmethod
    def instance_to_values(instance: models.Bill) -> dict:
        return dataclasses.asdict(instance)

    @staticmethod
    def table_columns() -> tuple[sqlalchemy.Column, ...]:
        return (
            sa.Column(
                "uuid", UUID(), nullable=False, default=lambda: str(uuid.uuid4())
            ),
            sa.Column("amount", sa.Integer, nullable=False),
            sa.Column("last_calculated_fee", sa.Integer, default=0),
            sa.Column("label", sa.String, nullable=True),
            sa.Column("payor_type", sa.Enum(models.PayorType), nullable=False),
            sa.Column("payor_id", sa.BigInteger, nullable=False),
            sa.Column("procedure_id", sa.BigInteger, nullable=False),
            sa.Column("cost_breakdown_id", sa.BigInteger, nullable=False),
            sa.Column("payment_method", sa.Enum(models.PaymentMethod), nullable=False),
            sa.Column("payment_method_label", sa.String, nullable=True),
            sa.Column("payment_method_id", sa.String, nullable=True),
            sa.Column("payment_method_type", sa.Enum(PaymentMethodType), nullable=True),
            sa.Column("card_funding", sa.Enum(CardFunding), nullable=True),
            sa.Column("status", sa.Enum(models.BillStatus), nullable=False),
            sa.Column("error_type", sa.String, nullable=True),
            sa.Column("reimbursement_request_created_at", sa.DateTime, nullable=True),
            sa.Column("display_date", sa.String, nullable=True),
            # state tracking
            sa.Column("processing_at", sa.DateTime, nullable=True),
            sa.Column("paid_at", sa.DateTime, nullable=True),
            sa.Column("refunded_at", sa.DateTime, nullable=True),
            sa.Column("failed_at", sa.DateTime, nullable=True),
            sa.Column("cancelled_at", sa.DateTime, nullable=True),
            sa.Column("refund_initiated_at", sa.DateTime, nullable=True),
            sa.Column("processing_scheduled_at_or_after", sa.DateTime, nullable=True),
            sa.Column("is_ephemeral", sa.Boolean, nullable=False, default=False),
        )

    @classmethod
    def deserialize(  # type: ignore[override] # Return type "Bill" of"deserialize" incompatible with return type "Optional[Bill]" in supertype "BaseRepository"
        cls, row: Mapping[str, Any] | None
    ) -> models.Bill:
        if row is None:
            return  # type: ignore[return-value] # Return value expected
        # faux-json field for old mysql
        row_data = dict(row)
        # row_data["uuid"] = UUID(row_data["uuid"])
        row_data["payor_type"] = PayorType(row_data["payor_type"])
        row_data["status"] = BillStatus(row_data["status"])
        row_data["payment_method"] = models.PaymentMethod(row_data["payment_method"])
        # needed as loading from the repository is not the same as loading from the db
        if isinstance(row_data["uuid"], str):
            row_data["uuid"] = uuid.UUID(row_data["uuid"])

        # create the model object with only fields available and not from the row columns returned
        expected_fields = [field.name for field in dataclasses.fields(cls.model)]
        expected_data = {
            column_name: value
            for column_name, value in row_data.items()
            if column_name in expected_fields
        }
        return cls.model(**expected_data)

    def get_by_uuid(self, uuid: str) -> models.Bill | None:
        where = self.table.c.uuid == uuid
        result = self.execute_select(where=where)
        row = result.first()
        return self.deserialize(row=row)

    def get_by_ids(self, ids: list[int]) -> list[models.Bill]:
        where = self.table.c.id.in_(ids)
        result = self.execute_select(where=where)
        entries: list[models.Bill] = [
            self.deserialize(row) for row in result.fetchall()
        ]
        return entries

    def get_by_procedure(
        self,
        procedure_ids: list[int],
        payor_type: models.PayorType | None = None,
        payor_id: int | None = None,
        exclude_payor_types: list[models.PayorType] | None = None,
        status: list[models.BillStatus] | None = None,
        is_ephemeral: bool = False,
    ) -> list[models.Bill]:
        valid_payor_input = (payor_type, payor_id) == (None, None) or None not in (
            payor_type,
            payor_id,
        )
        if not valid_payor_input:
            raise TypeError(
                "Payor type and Payor ID are both required arguments if one is provided."
            )
        where = [
            self.table.c.procedure_id.in_(procedure_ids),
            self.table.c.is_ephemeral == is_ephemeral,
        ]
        if payor_type and payor_id:
            where.append(self.table.c.payor_type == payor_type)
            where.append(self.table.c.payor_id == payor_id)
        if exclude_payor_types:
            where.append(sa.not_(self.table.c.payor_type.in_(exclude_payor_types)))
        if status:
            where.append(self.table.c.status.in_(status))
        result = self.execute_select(where=sa.and_(*where))
        entries: list[models.Bill] = [
            self.deserialize(row) for row in result.fetchall()
        ]
        return entries

    def get_by_cost_breakdown_ids(
        self, cost_breakdown_ids: list[int]
    ) -> list[models.Bill]:
        where = [
            self.table.c.cost_breakdown_id.in_(cost_breakdown_ids),
            self.table.c.is_ephemeral == False,
        ]
        result = self.execute_select(where=sa.and_(*where))
        entries: list[models.Bill] = [
            self.deserialize(row) for row in result.fetchall()
        ]
        return entries

    def get_estimates_by_payor(
        self,
        payor_type: models.PayorType,
        payor_id: int,
    ) -> list[models.Bill]:
        query = """
                SELECT *
                FROM bill
                WHERE
                bill.status = :estimate_status AND
                bill.payor_type = :payor_type AND
                bill.payor_id = :payor_id AND
                bill.is_ephemeral = TRUE AND
                bill.processing_scheduled_at_or_after IS NULL
                ORDER BY bill.created_at DESC
                """
        results = self.session.execute(
            query,
            {
                "payor_id": payor_id,
                "payor_type": payor_type.value,
                "estimate_status": models.BillStatus.NEW.value,
            },
        ).fetchall()

        entries: list[models.Bill] = [self.deserialize(row) for row in results]
        return entries

    def get_member_estimates_by_procedures(
        self,
        procedure_ids: list[int],
    ) -> list[models.Bill]:
        where = [
            self.table.c.procedure_id.in_(procedure_ids),
            self.table.c.payor_type == models.PayorType.MEMBER,
            self.table.c.status == models.BillStatus.NEW.value,
            self.table.c.is_ephemeral == True,
            self.table.c.processing_scheduled_at_or_after == None,
        ]
        result = self.execute_select(where=sa.and_(condition for condition in where))  # type: ignore[arg-type] # Argument 1 has incompatible type "Generator[Any, None, None]"; expected "Union[ClauseElement, str, bool]"
        entries: list[models.Bill] = [
            self.deserialize(row) for row in result.fetchall()
        ]
        return entries

    def get_by_payor(
        self,
        payor_type: models.PayorType,
        payor_id: int,
        status: list[models.BillStatus] | None = None,
    ) -> list[models.Bill]:
        where = [
            self.table.c.payor_type == payor_type,
            self.table.c.payor_id == payor_id,
            self.table.c.is_ephemeral == False,
        ]
        if status:
            where.append(self.table.c.status.in_(status))
        result = self.execute_select(where=sa.and_(condition for condition in where))  # type: ignore[arg-type] # Argument 1 has incompatible type "Generator[Any, None, None]"; expected "Union[ClauseElement, str, bool]"
        entries: list[models.Bill] = [
            self.deserialize(row) for row in result.fetchall()
        ]
        return entries

    def count_by_payor_with_historic(
        self, payor_type: models.PayorType, payor_id: int
    ) -> int:
        """
        Counts all historical bills for pagination in the payments history endpoint.
        """

        query = """
                SELECT count(bill.id)
                FROM bill LEFT JOIN
                (
                    SELECT
                    bill_processing_record.bill_id AS bill_id,
                    bill_processing_record.transaction_id as trans_id
                    FROM bill_processing_record
                    WHERE bill_processing_record.transaction_id IS NOT NULL
                    GROUP BY bill_processing_record.bill_id
                ) AS bpr_with_trans
                ON bill.id = bpr_with_trans.bill_id
                WHERE
                bill.status in :historic_status AND
                bill.payor_type = :payor_type AND
                bill.payor_id = :payor_id AND 
                bill.is_ephemeral = False AND
                (
                    bill.status = 'PAID' OR bpr_with_trans.trans_id IS NOT NULL
                )
                """
        to_return = self.session.scalar(
            query,
            {
                "payor_id": payor_id,
                "payor_type": payor_type.value,
                "historic_status": [s.value for s in models.HISTORIC_STATUS],
            },
        )
        return to_return

    def get_by_payor_with_historic(
        self,
        payor_type: models.PayorType,
        payor_id: int,
        historic_limit: int,
        historic_offset: int = 0,
    ) -> list[models.Bill]:
        query = """
                (
                    SELECT *
                    FROM bill
                    WHERE
                    bill.status in :upcoming_status  AND
                    bill.payor_type = :payor_type AND
                    bill.payor_id = :payor_id AND
                    bill.is_ephemeral = False 
                    ORDER BY id DESC
                )
                UNION
                (
                    SELECT bill.*
                    FROM bill LEFT JOIN
                    (
                        SELECT
                        bill_processing_record.bill_id AS bill_id,
                        bill_processing_record.transaction_id as trans_id
                        FROM bill_processing_record
                        WHERE bill_processing_record.transaction_id IS NOT NULL
                        GROUP BY bill_processing_record.bill_id
                    ) AS bpr_with_trans
                    ON bill.id = bpr_with_trans.bill_id
                    WHERE
                    bill.status in :historic_status AND
                    bill.payor_type = :payor_type AND
                    bill.payor_id = :payor_id AND
                    bill.is_ephemeral = False 
                    AND (
                        bill.status = 'PAID' OR bpr_with_trans.trans_id IS NOT NULL
                    )
                    ORDER BY id DESC
                    LIMIT :historic_limit
                    OFFSET :historic_offset
                )
                """

        results = self.session.execute(
            query,
            {
                "payor_id": payor_id,
                "payor_type": payor_type.value,
                "upcoming_status": [s.value for s in models.UPCOMING_STATUS],
                "historic_status": [s.value for s in models.HISTORIC_STATUS],
                "historic_limit": historic_limit,
                "historic_offset": historic_offset,
            },
        ).fetchall()

        entries: list[models.Bill] = [self.deserialize(row) for row in results]
        return entries

    def get_by_payor_types_statuses_date_range(
        self,
        payor_types: Optional[Iterable[models.PayorType]] = None,
        statuses: Optional[Iterable[models.BillStatus]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[models.Bill]:
        """
        Gets bills of specified payor types and state withe creat time in the specified range. Will throw if all
        parameters are none
        @param payor_types: The payor types to filter by.
        @type payor_types: Optional Iterable models.PayorType
        @param statuses: The status types to filter by.
        @type statuses: Optional Iterable models.BillStatus
        @param start_date: Starting date of the date range - evaluates to starting date 00:00
        @type start_date: Optional date
        @param end_date: Ending  date of the date range - evaluates to starting date 23:59
        @type end_date: Optional date
        @return: list of models.Bill objects
        @rtype: list
        """
        start_date_time = (
            datetime.combine(start_date, datetime.min.time()) if start_date else None
        )
        end_date_time = (
            datetime.combine(end_date, datetime.max.time()) if end_date else None
        )
        to_return = self.get_by_payor_type_statuses_date_time_range(
            payor_types, statuses, start_date_time, end_date_time
        )
        return to_return

    def get_by_payor_type_statuses_date_time_range(
        self,
        payor_types: Optional[Iterable[models.PayorType]] = None,
        statuses: Optional[Iterable[models.BillStatus]] = None,
        start_date_time: Optional[datetime] = None,
        end_date_time: Optional[datetime] = None,
    ) -> list[models.Bill]:
        """
        Gets bills of specified payor types and state with the created time in the specified range. Will throw if all
        parameters are none
        @param payor_types: The payor types to filter by.
        @type payor_types: Optional Iterable models.PayorType
        @param statuses: The status types to filter by.
        @type statuses: Optional Iterable models.BillStatus
        @param start_date_time: Starting datetime of the datetime range
        @type start_date_time: Optional datetime
        @param end_date_time: Ending datetime of the datetime range
        @param procedure_ids: Optional iterable of ints representing treatment procedure IDs to query for
        @type end_date_time: Optional datetime
        @return: list of models.Bill objects
        @rtype: list
        """
        where_clauses = []
        if start_date_time:
            where_clauses.append(self.table.c.created_at >= start_date_time)
        if end_date_time:
            where_clauses.append(self.table.c.created_at <= end_date_time)
        if payor_types:
            where_clauses.append(self.table.c.payor_type.in_(payor_types))
        if statuses:
            where_clauses.append(self.table.c.status.in_(statuses))
        if not where_clauses:
            raise ValueError("Provide at least one non-null conditional filter.")
        where_clauses.append(self.table.c.is_ephemeral == False)
        result = self.execute_select(where=sa.and_(*where_clauses))
        to_return: list[models.Bill] = [
            self.deserialize(row) for row in result.fetchall()
        ]
        return to_return

    def get_all_payor_ids_with_active_refunds(self) -> set[int]:
        """
        Gets all payor_id who have active refunds.
        @return: list of models.Bill objects
        @rtype: list
        """
        select = (
            sqlalchemy.select([self.table.c.payor_id])
            .where(self.table.c.amount < 0)
            .where(self.table.c.payor_type == PayorType.MEMBER)
            .where(self.table.c.is_ephemeral == False)
            .where(
                self.table.c.status.in_(
                    (
                        models.BillStatus.NEW,
                        models.BillStatus.FAILED,
                        models.BillStatus.PROCESSING,
                    )
                )
            )
        ).distinct()
        rows = self.session.execute(select).fetchall()
        to_return = {payor_id for payor_id, in rows}
        return to_return

    def get_failed_bills_by_payor_id_type_and_error_types(
        self,
        payor_id: int,
        payor_type: PayorType,
        exclude_refunds: bool = True,
        error_types: list[BillErrorTypes] | None = None,
    ) -> list[models.Bill]:
        where = [
            self.table.c.payor_type == payor_type,
            self.table.c.payor_id == payor_id,
            self.table.c.status == models.BillStatus.FAILED.value,
            self.table.c.is_ephemeral == False,
        ]
        if exclude_refunds:
            where.append(self.table.c.amount > 0)
        if error_types:
            where.append(self.table.c.error_type.in_([e.value for e in error_types]))
        result = self.execute_select(where=sa.and_(condition for condition in where))  # type: ignore[arg-type] # Argument 1 has incompatible type "Generator[Any, None, None]"; expected "Union[ClauseElement, str, bool]"
        to_return: list[models.Bill] = [
            self.deserialize(row) for row in result.fetchall()
        ]
        return to_return

    def get_new_bills_by_payor_id_and_type(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        payor_id: int,
        payor_type: PayorType,
        exclude_refunds: bool = True,
    ):
        where = [
            self.table.c.payor_type == payor_type,
            self.table.c.payor_id == payor_id,
            self.table.c.status == models.BillStatus.NEW.value,
            self.table.c.is_ephemeral == False,
        ]
        if exclude_refunds:
            where.append(self.table.c.amount > 0)
        result = self.execute_select(where=sa.and_(condition for condition in where))  # type: ignore[arg-type] # Argument 1 has incompatible type "Generator[Any, None, None]"; expected "Union[ClauseElement, str, bool]"
        to_return = [self.deserialize(row) for row in result.fetchall()]
        return to_return

    def get_new_bills_by_payor_ids_and_type_in_date_time_range(
        self,
        payor_ids: list[int],
        payor_type: PayorType,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> list[models.Bill]:
        where = [
            self.table.c.payor_type == payor_type,
            self.table.c.payor_id.in_(payor_ids),
            self.table.c.status == models.BillStatus.NEW.value,
            self.table.c.is_ephemeral == False,
            self.table.c.created_at.between(start_datetime, end_datetime),
        ]

        result = self.execute_select(where=sa.and_(condition for condition in where))  # type: ignore[arg-type] # Argument 1 has incompatible type "Generator[Any, None, None]"; expected "Union[ClauseElement, str, bool]"
        to_return: list[models.Bill] = [
            self.deserialize(row) for row in result.fetchall()
        ]
        return to_return

    def get_bills_by_procedure_id_payor_type_status(
        self,
        procedure_id: int,
        payor_type: PayorType,
        statuses: list[models.BillStatus],
    ) -> list[models.Bill]:
        """
        Given a procedure id and a payor type returns a list of associated bills.
        :param procedure_id: The procedure id
        :param payor_type: The payor type to filter by
        :param statuses: Statuses to filter by
        :return: The list of bills.
        """
        where = [
            self.table.c.payor_type == payor_type,
            self.table.c.procedure_id == procedure_id,
            self.table.c.is_ephemeral == False,
        ]
        if statuses:
            where.append(self.table.c.status.in_(statuses))
        result = self.execute_select(where=sa.and_(condition for condition in where))  # type: ignore[arg-type] # Argument 1 has incompatible type "Generator[Any, None, None]"; expected "Union[ClauseElement, str, bool]"
        to_return: list[models.Bill] = sorted(
            (self.deserialize(row) for row in result.fetchall()), key=lambda x: x.id  # type: ignore[arg-type,return-value] # Argument "key" to "sorted" has incompatible type "Callable[[Bill], Optional[datetime]]"; expected "Callable[[Bill], Union[SupportsDunderLT[Any], SupportsDunderGT[Any]]]"
        )
        return to_return

    def get_money_movement_bills_by_procedure_id_payor_type(
        self, procedure_id: int, payor_type: PayorType, bpr_table: sqlalchemy.Table
    ) -> list[models.Bill]:
        """
        Given a procedure id and a payor type, returns all the bills that had or could have money movement. This includes
        all PAID, NEW, PROCESSING, and FAILED bills. This also includes REFUNDED bills that were sent to the payment
        gateway. This excludes all CANCELLED bills and the REFUND bills that cancelled them.
        REFUND bills that initiated cancellations do not have transaction ids because there was no payment gateway
        interaction
        """
        query = """
        (
            SELECT bill.*
            FROM bill JOIN 
            (
                SELECT bill_processing_record.bill_id AS bill_id
                FROM bill_processing_record
                WHERE bill_processing_record.transaction_id IS NOT NULL 
                GROUP BY bill_processing_record.bill_id
            ) AS paid_bpr 
            ON bill.id = paid_bpr.bill_id
            WHERE bill.procedure_id = :procedure_id AND 
            bill.status = 'REFUNDED' AND
            bill.payor_type = :payor_type AND
            bill.is_ephemeral = False
            
        )
        UNION
        (
            SELECT *
            FROM bill
            WHERE 
            bill.procedure_id = :procedure_id AND 
            bill.status NOT IN ('CANCELLED', 'REFUNDED') AND
            bill.payor_type = :payor_type AND
            bill.is_ephemeral = False
        ) 
        ORDER BY id
        """
        raw_res = self.session.execute(
            query, {"procedure_id": procedure_id, "payor_type": payor_type.value}
        ).fetchall()

        to_return: list[models.Bill] = [self.deserialize(res) for res in raw_res]

        log.info(
            "Queried for money movement bills",
            procedure_id=procedure_id,
            payor_type=payor_type.value,
            query=str(query),
            bill_cnt=len(to_return),
            bill_ids=",".join(str(b.id) for b in to_return),
            bill_uuids=",".join(str(b.uuid) for b in to_return),
        )
        return to_return

    def get_procedure_ids_with_ephemeral_bills(
        self, procedure_ids: list[int]
    ) -> list[int]:
        """Filters treatment procedure ids for those that have active ephemeral bills"""
        if not procedure_ids:
            return []
        query = """
            SELECT DISTINCT b.procedure_id as tp_id
            FROM bill b
            WHERE b.procedure_id IN :procedure_ids
              AND b.status = 'NEW'
              AND b.is_ephemeral;  
        """
        raw_res = self.session.execute(
            query,
            {
                "procedure_ids": procedure_ids,
            },
        ).fetchall()
        to_return = [res.tp_id for res in raw_res]
        log.info(
            "Queried for procedure ids with active ephemeral bills.",
            bill_query=str(query),
            procedure_cnt=len(to_return),
            procedure_ids=",".join(str(id) for id in to_return),
        )
        return to_return

    def get_procedure_ids_with_non_ephemeral_bills(
        self, procedure_ids: list[int]
    ) -> list[int]:
        """Filters treatment procedure ids for those that have non-ephemeral bills"""
        if not procedure_ids:
            return []
        query = """
                SELECT DISTINCT b.procedure_id as tp_id
                FROM bill b
                WHERE b.procedure_id IN :procedure_ids
                  AND NOT b.is_ephemeral;
            """
        raw_res = self.session.execute(
            query,
            {
                "procedure_ids": procedure_ids,
            },
        ).fetchall()
        to_return = [res.tp_id for res in raw_res]
        log.info(
            "Queried for procedure ids with non-ephemeral bills.",
            bill_query=str(query),
            procedure_cnt=len(to_return),
            procedure_ids=",".join(str(id) for id in to_return),
        )
        return to_return

    def get_money_movement_bills_by_procedure_ids_payor_type_ytd(
        self,
        procedure_ids: list[int],
        payor_type: PayorType,
        bpr_table: sqlalchemy.Table,
    ) -> list[models.Bill]:
        """
        Given many procedure ids and a payor type, returns all the bills that had or could have money movement year to
        date. This includes all PAID, NEW, PROCESSING, and FAILED bills. This also includes REFUNDED bills that were
        sent to the payment gateway. This excludes all CANCELLED bills and the REFUND bills that cancelled them.
        REFUND bills that initiated cancellations do not have transaction ids because there was no payment gateway
        interaction
        """
        query = """
       (
            SELECT bill.*
            FROM bill JOIN 
            (
                SELECT bill_processing_record.bill_id AS bill_id
                FROM bill_processing_record
                WHERE bill_processing_record.transaction_id IS NOT NULL
                AND EXTRACT(YEAR FROM bill_processing_record.created_at) 
                GROUP BY bill_processing_record.bill_id
            ) AS paid_bpr 
            ON bill.id = paid_bpr.bill_id
            WHERE bill.procedure_id IN :procedure_ids
            AND bill.status = 'REFUNDED'
            AND bill.payor_type = :payor_type
            AND bill.is_ephemeral = False
        )
        UNION
        (
            SELECT *
            FROM bill
            WHERE 
            bill.procedure_id IN :procedure_ids 
            AND bill.status NOT IN ('CANCELLED', 'REFUNDED')
            AND bill.payor_type = :payor_type
            AND EXTRACT(YEAR FROM bill.created_at) = EXTRACT(YEAR FROM CURRENT_DATE)
            AND bill.is_ephemeral = False
        ) 
        ORDER BY id
                """
        raw_res = self.session.execute(
            query, {"procedure_ids": procedure_ids, "payor_type": payor_type.value}
        ).fetchall()

        to_return: list[models.Bill] = [self.deserialize(res) for res in raw_res]

        log.info(
            "Queried for money movement bills",
            procedure_id=procedure_ids,
            payor_type=payor_type.value,
            query=str(query),
            bill_cnt=len(to_return),
            bill_ids=",".join(str(b.id) for b in to_return),
            bill_uuids=",".join(str(b.uuid) for b in to_return),
        )
        return to_return

    @trace_wrapper
    def get_processable_new_member_bills(
        self, *, processing_time_threshhold: datetime
    ) -> list[models.Bill]:
        """
        Returns all new member bills with processing_scheduled_at_or_after before the processing_time_threshhold.
        :param processing_time_threshhold:
        :return: A possibly empty list of bills
        """

        query = """
                SELECT *
                FROM bill
                WHERE
                bill.status = 'NEW' AND
                bill.payor_type = 'MEMBER' AND
                bill.processing_scheduled_at_or_after IS NOT NULL AND 
                bill.is_ephemeral = False AND
                bill.processing_scheduled_at_or_after <= :processing_time_threshhold                    
                """
        processing_time_threshhold = processing_time_threshhold.strftime(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", variable has type "datetime")
            "%Y-%m-%d %H:%M:%S"
        )
        raw_res = self.session.execute(
            query,
            {
                "processing_time_threshhold": processing_time_threshhold,
            },
        ).fetchall()
        to_return: list[models.Bill] = [self.deserialize(res) for res in raw_res]
        log.info(
            "Queried for NEW MEMBER in a range or before threshhold.",
            bill_query=str(query),
            bill_cnt=len(to_return),
            bill_processing_time_threshhold=processing_time_threshhold,
            bill_ids=",".join(str(b.id) for b in to_return),
        )
        return to_return
