Marshmallow CLI
---------------

A Cli help marshmallow v1 to v3 migration, supports:
   * Print a given schema into key and inferred type json as output
   * Generate OpenAPI spec based on the provided schema and path(optional) **Additional packages installation needed, please check the instruction details**
   * Stub data generation based on given schema
   * Compare V1 and V3 schema based on generated stub
   * Coverage calculation based on source schema and serialized/deserialized(optional) results

The goal of this cli is to provide utility function as well as stats calculation to facilitate 
marshmallow v1 to v3 migration in Maven, we want to
get a sense of fields being touched during serialization, increase confidence on the breadth and correctness of the
migrated results.

Note
----
* The inferred type has a lot of rooms to improve since our v1 schema doesn't has any typing information, so this
  tool is trying its best to infer field type, esp. for field defined with `fields.Method`
* the actual results should be less than the actual coverage number, since we have a bunch
of conditional logic in fields.Method doing exclude, schema choosing. The approach here just
get the full schema even if it's nested with excluding
* If you have nested schemas that don't live in the shared schema classes (`views.schemas.common` for v1 and
`views.schemas.base` for v3) use the --nested-schema-location and --nested-schema-location-v3 flags to set the
path location for your nested schemas, like `messaging.schemas.messaging`

Usage:
-----

* **Generate unit test for schema being migrated**:
------------------------------------------------------

```bash
  poetry run python scripts/ma_coverage_tool.py --schema-path "views.profiles:V2VerticalSchema" --v1-schema --compare-schema-path "views.schemas.base:V2VerticalSchemaV3" --generate-test
```

Example output:

in `test_schema_backwards_compatibility.py`

```python
 def test_v2_vertical_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.schemas.common import V2VerticalSchema
        from views.schemas.base import V2VerticalSchemaV3

        data = {'pluralized_display_name': 'Sample text', 'name': 'Sample text', 'can_prescribe': False, 'filter_by_state': True, 'description': 'Sample text', 'long_description': 'Sample text', 'id': 1}
        v1_schema = V2VerticalSchema()
        v3_schema = V2VerticalSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(data), "Backwards compatibility broken between versions"
        


        edge_case = {'pluralized_display_name': None, 'name': None, 'can_prescribe': None, 'filter_by_state': None, 'description': None, 'long_description': None, 'id': None}
        v1_schema = V2VerticalSchema()
        v3_schema = V2VerticalSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(edge_case), "Backwards compatibility broken between versions"
```

Adding `--check-deserialize` will include checking for `deserialization` process

* **Get PractitionersSchema Schema in json only**:
------------------------------------------------------

```bash
  poetry run python scripts/ma_coverage_tool.py --schema-path "views.profiles:PractitionersSchema"  --show-schema  --v1-schema
```

Example output (partial):
```bash
{
    "data": [
        {
            "subscription_plans": [
                {
                    "plan_payer": {
                        "email_confirmed": "<class 'bool'>",
                        "email_address": "typing.Any"
                    },
                    "total_segments": "<class 'int'>",
                    "first_cancellation_date": "<class 'datetime.datetime'>",
                    "api_id": "<class 'str'>",
                    "plan": {
                        "price_per_segment": "typing.Any",
                        "billing_description": "<class 'str'>",
                        "segment_days": "<class 'int'>",
                        "minimum_segments": "<class 'int'>",
                        "id": "<class 'int'>",
                        "description": "<class 'str'>",
                        "is_recurring": "<class 'bool'>",
                        "active": "<class 'bool'>"
                    },
                    "is_claimed": "<class 'bool'>",
                    "cancelled_at": "<class 'datetime.datetime'>",
                    "started_at": "<class 'datetime.datetime'>"
                }
            ],
            "test_group": "<class 'str'>",
            "middle_name": "<class 'str'>",
            "last_name": "<class 'str'>",
            "name": "typing.Any",
            "role": "typing.Any",
            "encoded_id": "typing.Any",
            "image_id": "<class 'int'>",
            "id": "<class 'int'>",
            "image_url": "typing.Any",
            "created_at": "<class 'datetime.datetime'>",
            "organization": {
                "name": "<class 'str'>",
                "vertical_group_version": "<class 'str'>",
                "education_only": "<class 'bool'>",
                "rx_enabled": "<class 'bool'>",
                "id": "<class 'int'>",
                "bms_enabled": "<class 'bool'>"
            },
            "avatar_url": "<class 'str'>",
            "country": {
                "summary": "typing.Any",
                "abbr": "typing.Any",
                "name": "typing.Any",
                "ext_info_link": "typing.Any"
            },
```

* **Get PractitionersSchema Stub data for testing purpose**:
------------------------------------------------------

```bash
  poetry run python scripts/ma_coverage_tool.py --schema-path "views.profiles:PractitionersSchema"  --generate-stub --v1-schema
```

Example output:
```bash
{
    "pagination": {
        "total": 53742,
        "limit": 73890,
        "order_direction": null,
        "offset": 7861
    },
    "meta": null,
    "data": [
        {
            "subscription_plans": [
                {
                    "api_id": "Sample text",
                    "cancelled_at": "2024-02-06T21:20:19.215731",
                    "is_claimed": true,
                    "plan": {
                        "description": "Sample text",
                        "price_per_segment": null,
                        "billing_description": "Sample text",
                        "minimum_segments": 97311,
                        "segment_days": 69747,
                        "is_recurring": false,
                        "active": true,
                        "id": 57761
                    },
                    "plan_payer": {
                        "email_confirmed": true,
                        "email_address": null
                    },
                    "total_segments": 58363,
                    "first_cancellation_date": "2024-02-06T21:20:19.215753",
                    "started_at": "2024-02-06T21:20:19.215755"
                }
            ],
            "role": null,
            "username": null,
            "profiles": {
                "practitioner": {

```

* **Check if PractitionersSchema and PractitionersSchemaV3 can serialize to the same results**:
------------------------------------------------------
```bash
 poetry run python scripts/ma_coverage_tool.py --schema-path "views.profiles:PractitionersSchema" --v1-schema --compare-schema-path "views.profiles:PractitionersSchemaV3"
```

Example output
```bash
Results are the same between <PractitionersSchema(many=False, strict=True)> and <PractitionersSchemaV3(many=False)>
```

* **Get coverage result for PractitionersSchemaV3 results**:
------------------------------------------------------

```bash
   poetry run python scripts/ma_coverage_tool.py --schema-path "views.profiles:PractitionersSchemaV3" --data-file "<PATH TO Results JSON>"
   python scripts/...  will be fine too if your virtualenv is enabled
```
Example data json:
```json
{
  12313: {data: [{}], pagination: {}, meta: None}
}

```

* **Generate OpenAPI Spec based on provided v3 schema and path(optional)** *
----------------------------------------------------------------------
First, make sure you install the two packages help with the openapi spec generation
```bash
pip install apispec==4.7.1  # for general openapi spec
pip install apispec-webframeworks==0.5.2  # for flask resource
```
Then:

Generate openapi spec with path:

```bash
 python scripts/ma_coverage_tool.py --schema-path "views.profiles:PractitionersSchemaV3" --show-schema --openapi-spec --openapi-path "/api/v1/practitioners"
```


