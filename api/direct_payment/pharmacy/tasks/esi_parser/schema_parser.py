import csv
from dataclasses import dataclass
from typing import Dict, List, Optional, TextIO, Union

from direct_payment.pharmacy.tasks.esi_parser.schema_extractor import (
    Column,
    FixedWidthSchema,
    SchemaExtractor,
)


@dataclass
class ESIRow:
    name: str
    raw_value: str
    raw_type: str
    converted_val: Optional[Union[str, int, float]] = None


class SchemaParser:
    _fields: List[FixedWidthSchema] = []

    def __init__(
        self, schema: TextIO, columns: List[Column] = None, one_based: bool = True  # type: ignore[assignment] # Incompatible default for argument "columns" (default has type "None", argument has type "List[Column]")
    ):
        schema_reader = csv.reader(schema)
        schema_extractor = SchemaExtractor(
            next(schema_reader), columns=columns, one_based=one_based
        )

        for i, row in enumerate(schema_reader):
            try:
                self._fields.append(schema_extractor(row))
            except Exception as e:
                raise ValueError(f"Error reading schema at line {i+2}: {e}")

    def fields(self) -> List[FixedWidthSchema]:
        return self._fields

    def parse(self, line) -> List[ESIRow]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        values = []
        for field in self._fields:
            values.append(
                ESIRow(
                    name=field.name.strip(),
                    raw_type=field.data_type,
                    raw_value=(line[field.start : field.start + field.length].strip()),
                )
            )

        return values

    def parse_dict(self, line) -> Dict[FixedWidthSchema, ESIRow]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        return dict(zip(self.fields(), self.parse(line)))
