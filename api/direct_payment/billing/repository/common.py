from __future__ import annotations

import json
import uuid

from sqlalchemy import types
from sqlalchemy.dialects.mysql import CHAR


class UUID(types.TypeDecorator):
    impl = CHAR

    def __init__(self, allow_none=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.impl.length = 36
        self.allow_none = allow_none
        types.TypeDecorator.__init__(self, length=self.impl.length)

    def process_bind_param(self, value, dialect=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            if self.allow_none:
                return value
            else:
                raise ValueError("None is not a valid uuid.UUID")

        if value and isinstance(value, uuid.UUID):
            return str(value)
        if value and isinstance(value, str):
            try:
                _ = uuid.UUID(value)
                return str(value)
            except ValueError:
                raise ValueError(f"string {value} is not a valid uuid.UUID")
        raise ValueError(f"value {value} is not a valid uuid.UUID")

    def process_result_value(self, value, dialect=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value:
            return uuid.UUID(hex=value)
        return None

    def is_mutable(self) -> bool:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return False


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, uuid.UUID):
            # if the obj is uuid, we simply return the value of uuid
            return obj.hex
        return json.JSONEncoder.default(self, obj)
