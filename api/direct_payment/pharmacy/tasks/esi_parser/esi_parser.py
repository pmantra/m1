from typing import Dict, List, Tuple

from direct_payment.pharmacy.tasks.esi_parser.esi_converter import create_dataclasses
from direct_payment.pharmacy.tasks.esi_parser.schema_extractor import (
    Column,
    FixedWidthSchema,
)
from direct_payment.pharmacy.tasks.esi_parser.schema_parser import ESIRow, SchemaParser


class ESIParser:
    def __init__(self, schema_file_path: str):
        schema_file = open(schema_file_path)
        columns = [
            Column(normalized="column", name="Field Name"),
            Column(normalized="start", name="Starting Position"),
            Column(normalized="length", name="Length"),
            Column(normalized="data_type", name="Data Type"),
        ]
        self.parser = SchemaParser(schema_file, columns=columns, one_based=True)
        schema_file.close()

    @staticmethod
    def _process_record(
        record: Dict[FixedWidthSchema, ESIRow]
    ) -> Dict[FixedWidthSchema, Tuple]:
        return {k: (v.raw_value, v.raw_type) for k, v in record.items()}

    def parse(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, raw_file_path: str, kclass=None
    ) -> List[Dict[FixedWidthSchema, Tuple]]:
        results = []
        with open(raw_file_path, "rb") as fin:
            # Skip first and last row
            next(fin)
            prev = fin.readline()
            for line in fin:
                results.append(self._process_record(self.parser.parse_dict(prev)))
                prev = line

            return results

    def create_klass(self, class_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return create_dataclasses(class_name, self.parser.fields())
