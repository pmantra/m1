import json
import os

import pytest

from payer_accumulator.edi.errors import X12FileWriterException
from payer_accumulator.edi.x12_file_writer import X12FileWriter


@pytest.fixture(scope="function")
def schema_837():
    file_path = os.path.join(os.path.dirname(__file__), "../../../edi/models/837.json")
    with open(file_path, "r") as schema_file:
        schema = json.load(schema_file)
    return schema


@pytest.fixture(scope="function")
def x12_file_writer_with_837_schema(schema_837):
    return X12FileWriter(schema=schema_837)


class TestX12FileWriter:
    def test_find_segments(self):
        schema = {
            "$defs": {
                "segments": {
                    "segment_1": {
                        "abbreviation": "s1",
                        "properties": {
                            "test_property_1": {"type": "string"},
                            "test_property_2": {"type": "number"},
                        },
                    }
                }
            }
        }
        writer = X12FileWriter(schema)
        assert writer.segments == {
            "segment_1": {
                "abbreviation": "s1",
                "fields": [(1, "test_property_1"), (2, "test_property_2")],
            }
        }

    def test_find_segments_missing_information(self):
        schema_missing_abbreviation = {
            "$defs": {
                "segments": {
                    "segment_1": {
                        "properties": {
                            "test_property_1": {"type": "string"},
                            "test_property_2": {"type": "number"},
                        }
                    }
                }
            }
        }
        with pytest.raises(X12FileWriterException) as e:
            X12FileWriter(schema_missing_abbreviation)
            assert str(e) == "Missing abbreviation or properties for segment segment_1"

    def test_find_segments_with_positions(self):
        schema = {
            "$defs": {
                "segments": {
                    "segment_1": {
                        "abbreviation": "s1",
                        "positions": [2, 3],
                        "properties": {
                            "test_property_1": {"type": "string"},
                            "test_property_2": {"type": "number"},
                        },
                    }
                }
            }
        }
        writer = X12FileWriter(schema)
        assert writer.segments == {
            "segment_1": {
                "abbreviation": "s1",
                "fields": [(2, "test_property_1"), (3, "test_property_2")],
            }
        }

    def test_generate_x12_file(self, x12_file_writer_with_837_schema):
        content = x12_file_writer_with_837_schema.generate_x12_file(
            {
                "interchange_control_header": {
                    "authorization_information_qualifier": "00"
                },
                "loop_1000A": [{"submitter_name": {"entity_identifier_code": 41}}],
            }
        ).read()
        assert content == "ISA*00~\nNM1*41~"

    def test_segment_not_exist_in_schema(self, x12_file_writer_with_837_schema):
        with pytest.raises(X12FileWriterException) as e:
            x12_file_writer_with_837_schema.generate_x12_file({"bad_segment": {}})
        assert str(e.value) == "No segment bad_segment find in the schema"
