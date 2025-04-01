ESI Parser Package
-------------------


This package provide a functionality for properly ingest ESI fixed width file based on
provided schema in CSV format.


Modules
-------

Schema Decoder
--------------
`schema_decoder`takes external schema csv and generate proper schema for ingesting fixed 
width file, there are four required columns:
* column - Normalized name representing field name from external source
* start - Starting position of the field
* length - Byte size of the field
* data_type - Type information for value

Since different sources may provide different column names for these concepts, there's a
`Column` class to help with this gap, example below show's a mapping from external source has column
named`Field Name` to `column` :
```python
Column(normalized="column", name="Field Name")
```

Decoder is used by `schema_parser` internally


Schema Parser
------

Schema Parser is takes decoder to generate schema records
and provide interface for client to parse input raw file via:

```python
SchemaParser.parse(line)
```

For now each line is converted into a `ESIRow` record
which contains following attributes:
```python
raw_name - source field name
raw_type - source field type
raw_value - source field value
converted_value - default to None, need perform proper transformation
                  logic to convert into Maven schema
```
------------------------------------------------------

ESI_Parser
----------

Interface deal with parser raw file, raw data type conversion

```python
parse(file_path) -> List[Document]
```

The schema of `Document` needs to be iron out


------------

ESI_Converter
-------------
Handle ESI specific data type conversion. For example:

`D2` represents number with two digits after decimal point
`D3` represents number with three digits after decimal point


CLI
-----------------------------------------------
`cli.py`

This is mainly a CLI for testing, debugging schema decoding process

You can play around this by:

```bash
poetry run python direct_payment/pharmacy/tasks/esi_parser/cli.py --raw_file_path=<Path to the raw file>
```

Below is an example with direct referencing lower level API:

```python
        # raw_file_path - fix width file
        # schema_file_path - path to the schema file
        target_f, schema_f = open(raw_file_path), open(schema_file_path)
        columns = [
            Column(normalized="column", name="Field Name"),
            Column(normalized="start", name="Starting Position"),
            Column(normalized="length", name="Length"),
            Column(normalized="data_type", name="Data Type"),
        ]

        # Construct SchemaParser based on schema, columns, and whether the schema is one_based
        # or not
        parser = SchemaParser(schema_f, columns=columns, one_based=True)

        # Consuming raw data file
        # Skip first line and last line, since it's for header and trailer schema
        for line in target_f.readlines()[1:-1]:

            record = parser.parse_dict(line)

            def construct_document(record):
                result = {}
                for k, v in record.items():
                    result[k.name] = (v.raw_value, v.raw_type)

                return result

            import pprint

            pprint.pprint(construct_document(record))
            logger.info(f"Length of record: {len(record)}")
            logger.info("\n")


```