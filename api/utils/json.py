import dataclasses
import decimal
import enum
import json as _json
import uuid
from collections.abc import Iterable, Mapping, MappingView
from datetime import date, time

import json_merge_patch
from marshmallow_v1 import Schema

from utils.log import logger

log = logger(__name__)


class SafeJSONEncoder(_json.JSONEncoder):
    """A JSON Encoder which extends the default encoder.

    Supports:
        - date/datetime/time
        - uuid
        - decimals
        - dataclasses
        - nametuples
        - custom mappings
        - arbitrary iterables
    """

    def default(self, o):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Do our best to serialize a value.

        If an error happens, log it and move on.

        Notes:
            We handle a blanket exception here because this is meant to be used on 'hot'
            paths which can't afford to fail, such as data export.
        """
        try:
            if isinstance(o, (date, time)):
                return o.isoformat()
            if isinstance(o, uuid.UUID):
                return str(o)
            if isinstance(o, enum.Enum):
                return o.value
            if isinstance(o, decimal.Decimal):
                return float(o)
            if dataclasses.is_dataclass(o):
                return dataclasses.asdict(o)
            # NamedTuple
            if isinstance(o, tuple) and hasattr(o, "_asdict"):
                return o._asdict()
            # Custom Mappings
            elif isinstance(o, (Mapping, MappingView)):
                return {**o}
            # Any iterable that isn't a list
            elif isinstance(o, Iterable) and not isinstance(o, (str, bytes, bytearray)):
                return [*o]
            else:
                log.warning(
                    "Got usupported type for JSON serialization.",
                    type=o.__class__,
                )
                return f"<Unsupported Type: {o.__class__.__name__!r}>"
        except Exception as e:
            log.warning(
                f"Got error serializing value: {e}",
                error=e.__class__.__name__,
                value=str(o),
            )
            return f"<Unsupported Type: {o.__class__.__name__!r}>"


def apply_merge_patch(target: object, changes: dict, schema: Schema):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    res = json_merge_patch.merge(schema.dump(target).data, changes)
    schema.validate(res)
    return res


def json_hook_restore_int_keys(x):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    JSON coerces all keys to strings. This can create confusion especially when
    push/pulling data from a JSON db col or a cache location. This function, to
    be used as a hook to json.loads, will restore integer keys to their original
    type.

    IMPORTANT: Values that begin as string representing integers (example "123")
    will be converted to integers on their way out. Use of this helper should be
    done with caution and only when you retain full control of the data format.

    Usage:
        value = json.loads(json_str, object_hook=json_hook_restore_int_keys)
    """
    if isinstance(x, dict):
        result = {}
        for k, v in x.items():
            try:
                k = int(k)
            except ValueError:
                pass
            result[k] = v
        return result
