from io import StringIO

from direct_payment.pharmacy.tasks.esi_parser.schema_extractor import FixedWidthSchema
from direct_payment.pharmacy.tasks.esi_parser.schema_parser import ESIRow, SchemaParser


def test_schema_line_parser():
    schema = """column,start,length,data_type
    foo,1,5,N
    bar,6,2,N
    baz,8,5,AN"""

    f = StringIO(schema)
    parser = SchemaParser(f)
    f.close()

    assert (
        FixedWidthSchema(name="foo", start=0, length=5, data_type="N")
        == parser.fields()[0]
    )
    assert (
        FixedWidthSchema(name="bar", start=5, length=2, data_type="N")
        == parser.fields()[1]
    )
    assert (
        FixedWidthSchema(name="baz", start=7, length=5, data_type="AN")
        == parser.fields()[2]
    )

    parsed = parser.parse("111112233333")
    assert ESIRow(name="foo", raw_value="11111", raw_type="N") == parsed[0]
    assert ESIRow(name="bar", raw_value="22", raw_type="N") == parsed[1]
    assert ESIRow(name="baz", raw_value="33333", raw_type="AN") == parsed[2]

    parsed = parser.parse("    1 2    3")
    assert ESIRow(name="foo", raw_value="1", raw_type="N") == parsed[0]
    assert ESIRow(name="bar", raw_value="2", raw_type="N") == parsed[1]
    assert ESIRow(name="baz", raw_value="3", raw_type="AN") == parsed[2]

    parsed = parser.parse("1  1  233  3")
    assert ESIRow(name="foo", raw_value="1  1", raw_type="N") == parsed[0]
    assert ESIRow(name="bar", raw_value="2", raw_type="N") == parsed[1]
    assert ESIRow(name="baz", raw_value="33  3", raw_type="AN") == parsed[2]
