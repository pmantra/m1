from direct_payment.pharmacy.tasks.esi_parser.schema_extractor import SchemaExtractor


def test_schema_extractor_init():
    extractor = SchemaExtractor(["column", "start", "length", "data_type"])
    assert 1 == extractor.start
    assert 3 == extractor.data_type
    assert 2 == extractor.length
    assert 0 == extractor.column
