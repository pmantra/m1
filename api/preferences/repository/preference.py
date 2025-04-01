from __future__ import annotations

import ddtrace
from sqlalchemy import Column, String, UniqueConstraint

from preferences import models
from storage.repository import abstract, base

__all__ = ("PreferenceRepository",)


class PreferenceRepository(base.BaseRepository[models.Preference]):  # type: ignore[type-var] # Type argument "Preference" of "BaseRepository" must be a subtype of "Instance"
    model = models.Preference

    @classmethod
    def table_name(cls) -> str:
        return "preference"

    @staticmethod
    def table_columns() -> tuple[Column, ...]:
        return (  # type: ignore[return-value] # Incompatible return value type (got "Tuple[Column[Optional[Any]], Column[Optional[Any]], Column[Optional[Any]], UniqueConstraint]", expected "Tuple[Column[Any], ...]")
            Column("name", String),
            Column("default_value", String),
            Column("type", String),
            UniqueConstraint("name"),
        )

    @staticmethod
    def instance_to_values(instance: abstract.InstanceT) -> dict:  # type: ignore[override] # Signature of "instance_to_values" incompatible with supertype "BaseRepository"
        return dict(
            id=instance.id,
            name=instance.name,  # type: ignore[attr-defined] # "abstract.InstanceT" has no attribute "name"
            default_value=instance.default_value,  # type: ignore[attr-defined] # "abstract.InstanceT" has no attribute "default_value"
            type=instance.type,  # type: ignore[attr-defined] # "abstract.InstanceT" has no attribute "type"
        )

    @ddtrace.tracer.wrap()
    def get_by_name(self, *, name: str) -> models.Preference:
        where = self.table.c.name == name
        result = self.execute_select(where=where)
        row = result.first()
        return self.deserialize(row)  # type: ignore[return-value] # Incompatible return value type (got "Optional[Preference]", expected "Preference")
