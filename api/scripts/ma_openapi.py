import ast
import inspect
import os
from textwrap import dedent

import click

try:
    from apispec import APISpec
    from apispec.ext.marshmallow import MarshmallowPlugin, OpenAPIConverter
    from apispec.ext.marshmallow.field_converter import FieldConverterMixin
    from apispec_webframeworks.flask import FlaskPlugin

    apispec_available = True
except ImportError as e:  # noqa
    click.echo(
        click.style(  # noqa
            "Failed to import apispec related modules, this is required for openapi spec to be functioning",
            fg="red",
        )
    )
    apispec_available = False

from marshmallow import fields as ma_fields
from marshmallow import utils

if apispec_available:

    class MavenFieldConverterMixin(FieldConverterMixin):
        def init_attribute_functions(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
            super().init_attribute_functions()
            self.attribute_functions.append(self.method2properties)

        def method2properties(self, field, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            ret = {}
            if isinstance(field, ma_fields.Method):
                call = utils.callable_or_raise(
                    getattr(field.parent, field.serialize_method_name)  # type: ignore[arg-type] # error: Argument 2 to "getattr" has incompatible type "Optional[str]"; expected "str"
                )
                target_schema_name, many, inferred_type = find_schema_in_method(call)
                if target_schema_name:
                    schema_dict = self.resolve_nested_schema(target_schema_name)
                    if ret and "$ref" in schema_dict:
                        ret.update({"allOf": [schema_dict]})
                    else:
                        ret.update(schema_dict)
                else:
                    ret["type"] = inferred_type

            return ret

    class MavenOpenAPIConverter(MavenFieldConverterMixin, OpenAPIConverter):
        pass


class SchemaFinder(ast.NodeVisitor):
    """
    A AST finder to get nested Schema usage from parent marshmallow schema and infer return type based on return statement
    based on fields.Method's return statement

    """

    def __init__(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        super().__init__()
        self.target_schema_name = None
        self.many = False
        self.inferred_return_type = None

    def visit_Call(self, node):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(node.func, ast.Name) and "Schema" in node.func.id:
            if not self.target_schema_name:
                self.target_schema_name = node.func.id
                for kw in node.keywords:
                    if kw == "many":
                        self.many = kw.value
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "dump":
            for kw in node.keywords:
                if kw.arg == "many" and isinstance(kw.value, ast.Constant):
                    self.many = kw.value.value

        self.generic_visit(node)

    def inspect_return_type(self, node):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if hasattr(node, "body") and isinstance(node.body, list):
            for body in node.body:
                if isinstance(body, ast.Return):
                    if isinstance(body.value, ast.Str):
                        self.inferred_return_type = str
                    elif isinstance(body.value, ast.Constant):
                        self.inferred_return_type = type(body.value.value)

    def visit_FunctionDef(self, node):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if node.args.defaults:
            for default in node.args.defaults:
                if isinstance(default, ast.Name) and "Schema" in default.id:
                    self.target_schema_name = default.id
        self.inspect_return_type(node)
        self.generic_visit(node)


def get_openapi_spec(schema, path=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not apispec_available:
        return None
    mp = MarshmallowPlugin
    mp.Converter = MavenOpenAPIConverter
    spec = APISpec(
        title=f"Maven Clinic {schema.__name__}",
        version="1.0.0",
        openapi_version="3.1.0",
        plugins=[FlaskPlugin(), mp()],
    )
    if path:
        from app import create_app

        app = create_app()
        with app.test_request_context():
            for rule in app.url_map.iter_rules():
                if str(rule) == path:
                    spec.path(view=app.view_functions[rule.endpoint])

    spec.components.schema(schema.__name__, schema=schema())
    return spec


def output_to_yaml(spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    with open(f"{os.getcwd()}/scripts/openapi.yaml", "w") as fout:
        fout.write(spec.to_yaml())


def find_schema_in_method(call):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    source = dedent(inspect.getsource(call))
    tree = ast.parse(source)
    finder = SchemaFinder()
    finder.visit(tree)
    return finder.target_schema_name, finder.many, finder.inferred_return_type
