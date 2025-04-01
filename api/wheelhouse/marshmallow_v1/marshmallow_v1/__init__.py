# -*- coding: utf-8 -*-
from __future__ import absolute_import
import warnings

from marshmallow_v1.schema import (
    Schema,
    SchemaOpts,
    MarshalResult,
    UnmarshalResult,
    Serializer,
)
from marshmallow_v1.utils import pprint
from marshmallow_v1.exceptions import (
    MarshallingError,
    UnmarshallingError,
    ValidationError,
)

__version__ = "1.2.6"
__author__ = "Steven Loria"
__license__ = "MIT"

__all__ = [
    "Schema",
    "Serializer",
    "SchemaOpts",
    "pprint",
    "MarshalResult",
    "UnmarshalResult",
    "MarshallingError",
    "UnmarshallingError",
    "ValidationError",
]

warnings.warn("marshmallow_v1 has been deprecated and replaced with v3. Please import with the statement `import marshmallow` instead.", DeprecationWarning)
