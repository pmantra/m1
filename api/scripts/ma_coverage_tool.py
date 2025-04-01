"""
A Cli help verify marshmallow migration purpose, supports:
   * Coverage calculation based on source schema and serialized results

The goal of this cli is to provide stats during marshmallow v1 to v3 migration, we want to
get a sense of fields being touched during serialization.

Note the actual results should be less than the actual coverage number, since we have a bunch
of conditional logic in fields.Method doing exclude, schema choosing. The approach here just
get the full schema even if it's nested with excluding

Usage:

* Get coverage result for PractitionersSchema results:
  poetry run python scripts/ma_coverage_tool.py --schema-path "views.profiles:PractitionersSchema" --data-file "<PATH TO Results JSON>"  --v1-schema

* Get PractitionersSchema Schema in json only:
  poetry run python scripts/ma_coverage_tool.py --schema-path "views.profiles:PractitionersSchema"  --show-schema  --v1-schema

* Get PractitionersSchema Stub data for testing purpose:
  poetry run python scripts/ma_coverage_tool.py --schema-path "views.profiles:PractitionersSchema"  --generate-stub --v1-schema

* Check if the v1 and v3 schema can get the same serialize result:
  poetry run python scripts/ma_coverage_tool.py --schema-path "views.profiles:PractitionersSchema" --v1-schema --compare-schema-path "views.profiles:PractitionersSchemaV3"

* Get coverage result for PractitionersSchemaV3 results
   poetry run python scripts/ma_coverage_tool.py --schema-path "views.profiles:PractitionersSchemaV3" --data-file "<PATH TO Results JSON>"
   python scripts/...  will be fine too if your virtualenv is enabled

"""
import ast
import copy
import datetime
import io
import json
import os.path
import pprint
import random
import typing
from importlib import import_module

import click
from marshmallow import fields as v3_fields
from marshmallow_v1 import fields as v1_fields

from app import create_app
from scripts.ma_openapi import find_schema_in_method, get_openapi_spec, output_to_yaml

# ===== Mapping for marshmallow v1 and v3 fields type to python native types ===================

MA_V1_TO_PY_TYPE_MAPPER = {
    v1_fields.String: str,
    v1_fields.Str: str,
    v1_fields.Int: int,
    v1_fields.Email: str,
    v1_fields.Bool: bool,
    v1_fields.Integer: int,
    v1_fields.Float: float,
    v1_fields.Boolean: bool,
    v1_fields.URL: str,
    v1_fields.Url: str,
    v1_fields.DateTime: datetime.datetime,
    v1_fields.Date: datetime.date,
    v1_fields.Raw: typing.Any,
}

MA_V3_TO_PY_TYPE_MAPPER = {
    v3_fields.String: str,
    v3_fields.Str: str,
    v3_fields.Int: int,
    v3_fields.Integer: int,
    v3_fields.Email: str,
    v3_fields.Bool: bool,
    v3_fields.URL: str,
    v3_fields.Url: str,
    v3_fields.Float: float,
    v3_fields.Boolean: bool,
    v3_fields.DateTime: datetime.datetime,
    v3_fields.Date: datetime.date,
    v3_fields.Raw: typing.Any,
}
# ==============================================================================================

SCHEMA_COMPATIBILITY_TEST_PATH = (
    "views/pytests/schemas/test_schema_backwards_compatibility.py"
)


def callable_or_raise(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Check that an object is callable, else raise a :exc:`TypeError`."""
    if not callable(obj):
        raise TypeError("Object {!r} is not callable.".format(obj))
    return obj


def get_py_type(field, v1=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    d = MA_V1_TO_PY_TYPE_MAPPER if v1 else MA_V3_TO_PY_TYPE_MAPPER
    for ma_field, py_type in d.items():
        if isinstance(field, ma_field):
            return py_type
    # For fields defined as non-primitive type of doesn't have straightforward return type infer
    # fallback to typing.Any
    return typing.Any


def find(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    schema,
    exclude=None,
    v1=True,
    nested_schema_location=None,
    nested_schema_location_v3=None,
):  # noqa
    if exclude is None:
        exclude = []
    all_fields = {}
    if v1:
        module_name = "views.schemas.common"
        default_module = import_module(module_name)
        secondary_default_module = (
            None
            if nested_schema_location is None
            else import_module(nested_schema_location)
        )
    else:
        module_name = "views.schemas.base"
        default_module = import_module(module_name)
        secondary_default_module = (
            None
            if nested_schema_location_v3 is None
            else import_module(nested_schema_location_v3)
        )

    for f_name, field in schema.fields.items():
        f = v1_fields if v1 else v3_fields
        if isinstance(field, f.Nested):
            if f_name in exclude:
                continue
            if type(field.schema) == type(schema):  # noqa:  E721
                exclude.append(f_name)

            nested = find(
                field.schema,
                exclude=exclude,
                v1=v1,
                nested_schema_location=nested_schema_location,
                nested_schema_location_v3=nested_schema_location_v3,
            )
            if field.many:
                all_fields[f_name] = [nested]
            else:
                all_fields[f_name] = nested
        elif isinstance(field, f.Method):
            call = (
                callable_or_raise(getattr(schema, field.serialize_method_name))
                if not v1
                else callable_or_raise(getattr(schema, field.method_name))
            )
            target_schema_name, many, inferred_return_type = find_schema_in_method(call)
            if target_schema_name:
                # Normalize schema class name
                try:
                    # first try to get the class schema name from the base location
                    schema_cls = getattr(
                        default_module,
                        target_schema_name.rstrip("V1") if v1 else target_schema_name,
                    )
                except AttributeError as e:
                    # if we couldn't find the schema in the base location, try the secondary location
                    if secondary_default_module is not None:
                        schema_cls = getattr(
                            secondary_default_module,
                            target_schema_name.rstrip("V1")
                            if v1
                            else target_schema_name,
                        )
                    else:
                        raise e
                nested_schema = schema_cls()
                nested = find(
                    nested_schema,
                    v1=False if "V3" in target_schema_name else True,
                    nested_schema_location=nested_schema_location,
                    nested_schema_location_v3=nested_schema_location_v3,
                )
                all_fields[f_name] = [nested] if many else nested
            else:
                if inferred_return_type:
                    all_fields[f_name] = str(inferred_return_type)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", target has type "List[Any]")
                else:
                    all_fields[f_name] = str(get_py_type(field, v1=v1))  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", target has type "List[Any]")
        else:
            all_fields[f_name] = str(get_py_type(field, v1=v1))  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", target has type "List[Any]")
    return all_fields


def calculate_coverage(schema, json_data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def traverse_schema_and_data(schema, data, counters):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(schema, dict) and isinstance(data, dict):
            for key, val in schema.items():
                counters["total"] += 1
                if key in data:
                    counters["present"] += 1
                    if isinstance(val, dict):
                        traverse_schema_and_data(schema[key], data[key], counters)
                    elif (
                        isinstance(val, list)
                        and len(val) > 0
                        and isinstance(data[key], list)
                    ):
                        for item in data[key]:
                            traverse_schema_and_data(schema[key][0], item, counters)
        elif isinstance(schema, list) and len(schema) > 0 and isinstance(data, list):
            for item in data:
                traverse_schema_and_data(schema[0], item, counters)

    counters = {"total": 0, "present": 0}
    for _, d in json_data.items():
        traverse_schema_and_data(schema, d, counters)
    if counters["total"] > 0:
        return (counters["present"] / counters["total"]) * 100
    return 0


def import_class(import_str):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    module_name, class_name = import_str.rsplit(":", 1)
    module = import_module(module_name)
    return getattr(module, class_name)


def stub_value_by_type(type_hint):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if type_hint == str(str):
        return "Sample text"
    elif type_hint == str(int):
        # N.B. The range here has impact for results validation since our
        # serialization rely on database access and issue actual query.
        # One specific example is that in `UserSchema`, we will query user
        # object based on user_id which is generated randomly here, setting
        # [1, 2] simply because I only have 2 records in my local DB.
        return random.randint(1, 2)
    elif type_hint == str(float):
        return random.uniform(1.0, 100.0)
    elif type_hint == str(bool):
        return random.choice([True, False])
    elif type_hint == str(datetime.datetime):
        return datetime.datetime.now().replace(tzinfo=datetime.timezone.utc)
    elif type_hint == "typing.Any":
        return None


def generate_stub_data(schema):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if isinstance(schema, dict):
        return {key: generate_stub_data(value) for key, value in schema.items()}
    elif isinstance(schema, list):
        return [generate_stub_data(schema[0])] if schema else []
    elif isinstance(schema, str):
        return stub_value_by_type(schema)
    else:
        return None


def normalize_datetime_for_deserialize(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if isinstance(obj, dict):
        return {
            key: normalize_datetime_for_deserialize(value) for key, value in obj.items()
        }
    elif isinstance(obj, list):
        return [normalize_datetime_for_deserialize(item) for item in obj]
    elif isinstance(obj, datetime.datetime):
        naive_dt = obj.replace(tzinfo=None)
        return naive_dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return obj


def compare_schema_with_stub(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    origin_schema, latest_schema, v1_schema, result, check_deserialize
):
    with app.test_request_context():
        if v1_schema:
            origin_ser = origin_schema.dump(result).data
            latest_ser = latest_schema.dump(result)
            if check_deserialize:
                result = normalize_datetime_for_deserialize(result)
                origin_der = origin_schema.load(result).data
                latest_der = latest_schema.load(result)
        else:
            origin_ser = origin_schema.dump(result)
            latest_ser = latest_schema.dump(result).data

            if check_deserialize:
                result = normalize_datetime_for_deserialize(result)
                origin_der = origin_schema.load(result)
                latest_der = latest_schema.load(result).data

        if origin_ser != latest_ser:
            click.echo(
                f"There's difference between {origin_ser} and {latest_ser} in serialization",
                err=True,
            )
        else:
            click.echo(
                click.style(
                    f"Results are the same between {origin_schema} and {latest_schema} for serialization",
                    fg="green",
                )
            )

        if check_deserialize:
            if origin_der != latest_der:
                click.echo(
                    f"There's difference between {origin_der} and {latest_der} in deserialization",
                    err=True,
                )
            else:
                click.echo(
                    click.style(
                        f"Results are the same between {origin_schema} and {latest_schema} for deserialization",
                        fg="green",
                    )
                )


def normalize_schema_name(name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return "".join(["_" + i.lower() if i.isupper() else i for i in name]).lstrip("_")


class AutoGenStub(ast.NodeVisitor):
    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, test_file_path, original_schema, new_schema, gen_stub, check_deserialize
    ):
        self.test_file_path = test_file_path
        self.test_class_exists = False
        self.original_import_path, self.original_import_name = original_schema.rsplit(
            ":", 1
        )
        self.new_import_path, self.new_import_name = new_schema.rsplit(":", 1)
        self.gen_stub = gen_stub
        self.test_method_name = (
            f"test_{normalize_schema_name(self.original_import_name)}"
        )
        self.check_deserialize = check_deserialize

    def parse_test_file(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        with open(self.test_file_path, "r") as file:
            source = file.read()
            self.tree = ast.parse(source, filename=self.test_file_path)

        self.visit(self.tree)
        if not self.test_class_exists:
            self.add_test_class_and_method()

    def visit_ClassDef(self, node):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if node.name == "TestSchemaBackwardsCompatibility":
            self.test_class_exists = True
            for item in node.body:
                if (
                    isinstance(item, ast.FunctionDef)
                    and item.name == self.test_method_name
                ):
                    click.echo(
                        click.style(
                            f"Test method {self.test_method_name} already exists!",
                            fg="yellow",
                        )
                    )
                    return
            self.add_test_method_to_existing_class()

    def add_test_class_and_method(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation # noqa
        data_copy = copy.copy(self.gen_stub)
        self.gen_stub_edge(data_copy)
        with open(self.test_file_path, "a") as file:
            file.write(
                f"""

class TestSchemaBackwardsCompatibility:
    \"\"\"Auto generated class by scripts/ma_coverage_tool\"\"\"

    def {self.test_method_name}(self):
        \"\"\"
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        \"\"\"

        from {self.original_import_path} import {self.original_import_name}
        from {self.new_import_path} import {self.new_import_name}

        data = {self.gen_stub}
        v1_schema = {self.original_import_name}()
        v3_schema = {self.new_import_name}()
        assert v1_schema.dump(data).data == v3_schema.dump(data), "Backwards compatibility broken between versions"

        edge_case = {data_copy}
        v1_schema = {self.original_import_name}()
        v3_schema = {self.new_import_name}()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(edge_case), "Backwards compatibility broken between versions"

 """
            )

            click.echo(
                click.style(
                    f"Added TestSchemaBackwardsCompatibility and test method: {self.test_method_name}",
                    fg="green",
                )
            )

    def gen_stub_edge(self, edge_case):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for k, v in edge_case.items():
            if isinstance(v, dict):
                self.gen_stub_edge(v)
            else:
                edge_case[k] = None

    def add_test_method_to_existing_class(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation # noqa
        data_copy = copy.copy(self.gen_stub)
        self.gen_stub_edge(data_copy)
        deserialize_data = normalize_datetime_for_deserialize(self.gen_stub)

        with open(self.test_file_path, "a") as file:
            file.write(
                f"""
    def {self.test_method_name}(self):
        \"\"\"
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        \"\"\"
        from {self.original_import_path} import {self.original_import_name}
        from {self.new_import_path} import {self.new_import_name}

        data = {self.gen_stub}
        v1_schema = {self.original_import_name}()
        v3_schema = {self.new_import_name}()
        assert v1_schema.dump(data).data == v3_schema.dump(data), "Backwards compatibility broken between versions"
        {f'assert v1_schema.load({deserialize_data}).data == v3_schema.load({deserialize_data}), "Backwards compatibility broken between versions"' if self.check_deserialize else ''}


        edge_case = {data_copy}
        v1_schema = {self.original_import_name}()
        v3_schema = {self.new_import_name}()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(edge_case), "Backwards compatibility broken between versions"
        {'assert v1_schema.load(edge_case).data == v3_schema.load(edge_case), "Backwards compatibility broken between versions"' if self.check_deserialize else ''}
        """
            )
            click.echo(
                click.style(f"Added test method: {self.test_method_name}", fg="green")
            )


@click.command()
@click.option(
    "--schema-path",
    type=str,
    default=None,
    help="Path to the schema, in foo.bar:BazSchema format",
)
@click.option(
    "--data-file",
    type=click.Path(exists=True),
    default=None,
    help="Path to the JSON result file",
)
@click.option(
    "--show-schema",
    is_flag=True,
    help="Only show the schema with all fields plus corresponding typing information",
)
@click.option(
    "--v1-schema",
    is_flag=True,
    help="Whether provided schema is in marshmallow version V1 or V3",
)
@click.option(
    "--generate-stub",
    is_flag=True,
    help="Generate a sample JSON based on provided schema for unit testing purpose",
)
@click.option(
    "--compare-schema-path",
    type=str,
    default=None,
    help="Schema path doing correctness verification based on generated stub data, in foo.bar:BazSchema",
)
@click.option(
    "--generate-test",
    is_flag=True,
    help="Existing unit test path for auto generate unit test stub",
)
@click.option(
    "--check-deserialize",
    is_flag=True,
    default=False,
    help="Compare deserialization results for the given schema",
)
@click.option(
    "--openapi-spec",
    is_flag=True,
    default=False,
    help="Generate schema in openapi 3.1 format",
)
@click.option(
    "--openapi-path",
    type=str,
    default=None,
    help="Endpoint path for openapi spec, e.g. /api/v1/practitioners",
)
@click.option(
    "--nested-schema-location",
    type=str,
    default=None,
    help="Location of nested schemas in file(s) other than common",
)
@click.option(
    "--nested-schema-location-v3",
    type=str,
    default=None,
    help="Location of nested V3 schemas in file(s) other than common",
)
def main(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    schema_path,
    data_file,
    show_schema,
    v1_schema,
    generate_stub,
    compare_schema_path,
    generate_test,
    check_deserialize,
    openapi_spec,
    openapi_path,
    nested_schema_location,
    nested_schema_location_v3,
):
    SchemaClass = import_class(schema_path)
    instance = SchemaClass()

    schema_dict = find(
        instance,
        v1=v1_schema,
        nested_schema_location=nested_schema_location,
        nested_schema_location_v3=nested_schema_location_v3,
    )
    if show_schema:
        if openapi_spec and not v1_schema:
            spec = get_openapi_spec(SchemaClass, openapi_path)
            if spec:
                click.echo(
                    click.style(
                        json.dumps(spec.to_dict(), indent=4, default=str), fg="green"
                    )
                )
                output_to_yaml(spec)
            else:
                click.echo(
                    click.style(
                        "Make sure you have follow through README to have apispec related dependencies installed",
                        fg="Red",
                    )
                )
        else:
            click.echo(
                click.style(json.dumps(schema_dict, indent=4, default=str), fg="green")
            )
        return

    if generate_stub:
        result = generate_stub_data(schema_dict)
        buffer = io.StringIO()
        pp = pprint.PrettyPrinter(indent=4, stream=buffer)
        pp.pprint(result)  # noqa
        click.echo(click.style(buffer.getvalue(), fg="green"))
        if check_deserialize:
            click.echo(click.style("Stub for deserialization:", fg="green"))
            buffer = io.StringIO()
            result = normalize_datetime_for_deserialize(result)
            pp = pprint.PrettyPrinter(indent=4, stream=buffer)
            pp.pprint(result)  # noqa
            click.echo(click.style(buffer.getvalue(), fg="green"))
        return

    if compare_schema_path:
        schema_for_compare = import_class(compare_schema_path)
        schema_ins_for_compare = schema_for_compare()
        result = generate_stub_data(schema_dict)

        compare_schema_with_stub(
            instance, schema_ins_for_compare, v1_schema, result, check_deserialize
        )

        if generate_test:
            updater = AutoGenStub(
                test_file_path=f"{os.getcwd()}/{SCHEMA_COMPATIBILITY_TEST_PATH}",
                original_schema=schema_path,
                new_schema=compare_schema_path,
                gen_stub=result,
                check_deserialize=check_deserialize,
            )
            updater.parse_test_file()

        return

    if data_file:
        with open(data_file, "r") as fin:
            json_data = json.load(fin)

        coverage = calculate_coverage(schema_dict, json_data)
        click.echo(f"Coverage percentage: {coverage}%")


# Unfortunately since our serialization involves database query, we have to create a flask context to proceed
app = create_app()
if __name__ == "__main__":
    main()
