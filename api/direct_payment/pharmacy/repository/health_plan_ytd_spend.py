from __future__ import annotations

import dataclasses
from typing import Literal, Union

import ddtrace.ext
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import insert

from direct_payment.pharmacy.models.health_plan_ytd_spend import (
    HealthPlanYearToDateSpend,
    PlanType,
    Source,
)
from direct_payment.pharmacy.repository.util import transaction
from storage.connection import db
from storage.repository import base

trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class HealthPlanYearToDateSpendRepository(
    base.BaseRepository[HealthPlanYearToDateSpend]  # type: ignore[type-var] # Type argument "HealthPlanYearToDateSpend" of "BaseRepository" must be a subtype of "Instance"
):
    """
    Database access layer for health_plan_year_to_date_spend resource.
    """

    model = HealthPlanYearToDateSpend

    def __init__(
        self,
        session: sa.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
    ):
        # setting is_in_uow as true since it is hooked up with the transaction wrapper
        super().__init__(session=session or db.session, is_in_uow=True)

    @trace_wrapper
    def get_all_by_policy(self, *, policy_id: str, year: int) -> list[model]:  # type: ignore[valid-type] # Variable "direct_payment.pharmacy.repository.health_plan_ytd_spend.HealthPlanYearToDateSpendRepository.model" is not valid as a type
        """
        Return all rows by provided policy_id and year
        Args:
            policy_id: The policy_id value for query
            year: the year to query
        Returns:
            All matched rows
        """
        result = self.execute_select(
            where=sa.and_(
                self.table.c.policy_id == policy_id, self.table.c.year == year
            )
        )
        return self.deserialize_list(result.fetchall())  # type: ignore[arg-type] # Argument 1 to "deserialize_list" of "BaseRepository" has incompatible type "List[RowProxy]"; expected "Optional[List[Mapping[str, Any]]]"

    @trace_wrapper
    def get_all_by_member(
        self, *, policy_id: str, year: int, first_name: str, last_name: str
    ) -> list[model]:  # type: ignore[valid-type] # Variable "direct_payment.pharmacy.repository.health_plan_ytd_spend.HealthPlanYearToDateSpendRepository.model" is not valid as a type
        """
        Return all rows by provided policy_id, year, first_name and last_name
        Args:
            policy_id: The policy_id value for query
            year: the year to query
            first_name: member first name
            last_name: member last name
        Returns:
            All matched rows
        """
        result = self.execute_select(
            where=sa.and_(
                self.table.c.policy_id == policy_id,
                self.table.c.year == year,
                self.table.c.first_name == first_name,
                self.table.c.last_name == last_name,
            )
        )
        return self.deserialize_list(result.fetchall())  # type: ignore[arg-type] # Argument 1 to "deserialize_list" of "BaseRepository" has incompatible type "List[RowProxy]"; expected "Optional[List[Mapping[str, Any]]]"

    @trace_wrapper
    @transaction
    def batch_create(
        self, *, instances: list[model], fetch: Literal[True, False] = False  # type: ignore[valid-type] # Variable "direct_payment.pharmacy.repository.health_plan_ytd_spend.HealthPlanYearToDateSpendRepository.model" is not valid as a type
    ) -> Union[int, list[int]]:
        """
        Upsert a batch of records provided by client in a transaction, return affected row count

        Args:
            instances: A list of HealthPlanYearToDate instances
            fetch: Whether to get affected primary id or not
        Returns:
            the number of affected rows
        """
        statement = insert(table=self.table)

        upsert = statement.on_duplicate_key_update(
            deductible_applied_amount=statement.inserted.deductible_applied_amount,
            oop_applied_amount=statement.inserted.oop_applied_amount,
            policy_id=statement.inserted.policy_id,
        )
        result = self.session.execute(
            upsert, [self.instance_to_values(instance) for instance in instances]
        )
        if fetch:
            last_row_id = result.lastrowid
            first_row_id = last_row_id - len(instances) + 1
            return list(range(first_row_id, last_row_id + 1))

        return result.rowcount

    @trace_wrapper
    @transaction
    def create(self, *, instance: model, fetch: Literal[True, False] = True):  # type: ignore[no-untyped-def,valid-type] # Variable "direct_payment.pharmacy.repository.health_plan_ytd_spend.HealthPlanYearToDateSpendRepository.model" is not valid as a type
        return super().create(instance=instance)

    @trace_wrapper
    @transaction
    def update(self, *, instance: model, fetch: Literal[True, False] = True):  # type: ignore[no-untyped-def,valid-type] # Variable "direct_payment.pharmacy.repository.health_plan_ytd_spend.HealthPlanYearToDateSpendRepository.model" is not valid as a type
        return super().update(instance=instance)

    @trace_wrapper
    @transaction
    def delete(self, *, id: int) -> int:
        return super().delete(id=id)

    @staticmethod
    def instance_to_values(instance: model) -> dict:  # type: ignore[valid-type] # Variable "direct_payment.pharmacy.repository.health_plan_ytd_spend.HealthPlanYearToDateSpendRepository.model" is not valid as a type
        return dataclasses.asdict(instance)

    @staticmethod
    def table_columns() -> tuple[sa.Column, ...]:
        return (
            sa.Column(
                "id",
                sa.BigInteger,
                primary_key=True,
                autoincrement=True,
                nullable=False,
            ),
            sa.Column("policy_id", sa.String, nullable=False),
            sa.Column("year", sa.Integer, nullable=False),
            sa.Column("first_name", sa.String, nullable=False),
            sa.Column("last_name", sa.String, nullable=False),
            sa.Column(
                "source",
                sa.Enum(Source),
                default=Source.MAVEN,
                nullable=False,
            ),
            sa.Column(
                "plan_type",
                sa.Enum(PlanType),
                default=PlanType.INDIVIDUAL,
                nullable=False,
            ),
            sa.Column("deductible_applied_amount", sa.Integer, default=0),
            sa.Column("oop_applied_amount", sa.Integer, default=0),
            sa.Column("bill_id", sa.Integer, nullable=True),
            sa.Column("transmission_id", sa.String, nullable=True),
            sa.Column("transaction_filename", sa.String, nullable=True),
        )
