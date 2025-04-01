import io

from payer_accumulator.edi.constants import (
    COMPOSITE_FIELD_SEPARATOR,
    DATA_ELEMENT_SEPARATOR,
    NEW_LINE_SEPARATOR,
    SEGMENT_TERMINATOR,
)
from payer_accumulator.edi.errors import X12FileWriterException

SchemaT = dict


class X12FileWriter:
    """
    Class used to generate the actual x12 file based on EDI file schema
    """

    def __init__(self, schema: SchemaT):
        self.schema = schema
        self.segments: dict = self._find_segments(self.schema)

    @staticmethod
    def _find_segments(schema: SchemaT) -> dict:
        segments = {}

        segment_schemas = schema["$defs"]["segments"]
        for name, segment in segment_schemas.items():
            if segment.get("abbreviation") and segment.get("properties"):
                if "positions" not in segment:
                    positions = [i + 1 for i in range(len(segment["properties"]))]
                else:
                    positions = segment["positions"]
                segments[name] = dict(
                    abbreviation=segment["abbreviation"],
                    fields=list(zip(positions, segment["properties"].keys())),
                )
            else:
                raise X12FileWriterException(
                    f"Missing abbreviation or properties for segment {name}"
                )
        return segments

    def _convert_segment(self, segment_name: str, segment_data: dict) -> str:
        segment_schema = self.segments[segment_name]
        position_to_fields: list = segment_schema["fields"]

        line = [segment_schema["abbreviation"]] + [
            "" for _ in range(position_to_fields[-1][0])
        ]
        for position, field in position_to_fields:
            if field in segment_data:
                if isinstance(segment_data[field], dict):
                    line[position] = ""
                    for value in segment_data[field].values():
                        if line[position]:
                            # only append COMPOSITE_FIELD_SEPARATOR if it's not the first value
                            line[position] = line[position] + COMPOSITE_FIELD_SEPARATOR
                        if isinstance(value, list):
                            line[position] = line[
                                position
                            ] + COMPOSITE_FIELD_SEPARATOR.join(value)
                        else:
                            line[position] = line[position] + str(value)
                else:
                    if isinstance(segment_data[field], float):
                        line[position] = f"{segment_data[field]:.2f}"
                    else:
                        line[position] = str(segment_data[field])
        while line and line[-1] == "":
            line.pop()
        return f"{DATA_ELEMENT_SEPARATOR.join(line)}{SEGMENT_TERMINATOR}{NEW_LINE_SEPARATOR}"

    def _generate_x12_file(self, data: dict, loop_name: str = "") -> str:
        res = ""
        for name, value in data.items():
            segment_name = f"{loop_name}_{name}" if loop_name else name
            if segment_name in self.segments:
                res += self._convert_segment(
                    segment_name=segment_name, segment_data=value
                )
            elif name.startswith("loop"):
                for loop in value:
                    res += self._generate_x12_file(loop, loop_name=name)
            else:
                raise X12FileWriterException(
                    f"No segment {segment_name} find in the schema"
                )
        return res

    def generate_x12_file(self, data: dict) -> io.StringIO:
        """
        Given the data dictionary, generate the actual EDI file based on file schema
        """
        return io.StringIO(self._generate_x12_file(data).strip("\n"))
