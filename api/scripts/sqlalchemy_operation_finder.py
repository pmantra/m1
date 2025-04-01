"""
A simple script help checking for a given model, find out all sqlalchemy operations that could involve
a relationship and foreign key operation.

Example usage:

```bash
 python scripts/sqlalchemy_operation_finder.py --project-directory "/Users/<you>/gitlab.com/maven-clinic/maven/maven/api" --model-name "Appointment"

/Users/<you>/maven-clinic/maven/maven/api/appointments/tasks/appointment_notifications.py: Line 1188 - MemberAppointmentAck.query.join(Appointment)
/Users/<you>/maven-clinic/maven/maven/api/appointments/utils/booking.py: Line 156 - db.session.query(Schedule.id).filter(Schedule.user_id == member.id).join(Appointment, Schedule.id == Appointment.member_schedule_id)
/Users/<you>/maven-clinic/maven/maven/api/appointments/services/acknowledgement.py: Line 100 - db.session.query(MemberAppointmentAck).join(Appointment)
/Users/<you>/maven/maven/api/admin/views/models/payments.py: Line 216 - query.outerjoin(Appointment, Product)
/Users/<you>/maven/maven/api/members/utils/member_access.py: Line 34 - db.session.query(Schedule.user_id).join(Appointment)
/Users/<you>/maven/maven/api/views/profiles.py: Line 626 - db.session.query(Schedule.user_id).join(Appointment)

````

"""
import ast
import os

import click


class SQLAlchemyVisitor(ast.NodeVisitor):
    def __init__(self, filename, model_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.filename = filename
        self.relevant_operations = [
            "join",
            "outerjoin",
            "select_from",
            "with_parent",
            "filter",
            "filter_by",
            "order_by",
            "group_by",
            "having",
            "update",
            "delete",
            "subquery",
            "union",
            "intersect",
            "except_",
            "contains_eager",
            "lazyload",
            "joinedload",
            "subqueryload",
            "selectinload",
        ]
        self.model = model_name

    def visit_Call(self, node):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in self.relevant_operations and any(
                isinstance(arg, ast.Name) and arg.id == self.model for arg in node.args
            ):
                click.echo(
                    click.style(
                        f"{self.filename}: Line {node.lineno} - {ast.unparse(node)}",  # type: ignore[attr-defined] # Module has no attribute "unparse"
                        fg="green",
                    )
                )
        self.generic_visit(node)


@click.command()
@click.option(
    "--project-directory",
    type=str,
    default=None,
    help="Full path to the api project, e.g. /Users/<name>/.../api",
)
@click.option(
    "--model-name",
    type=str,
    default=None,
    help="Schema path doing correctness verification based on generated stub data, in foo.bar:BazSchema",
)
def main(project_directory, model_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    ignore_dirs = [
        "tests",
        "schemas",
        ".venv",
        "pytests",
        "venv",
        "wheelhouse",
    ]  # Add '.venv' to the ignored directories

    for subdir, dirs, files in os.walk(project_directory):
        dirs[:] = [d for d in dirs if d.lower() not in ignore_dirs]

        for file in files:
            if file.startswith("test_") or file.endswith("_test.py"):
                continue  # Skip test files
            filepath = os.path.join(subdir, file)
            if filepath.endswith(".py"):
                with open(filepath, "r") as fin:
                    try:
                        tree = ast.parse(fin.read(), filename=filepath)
                        visitor = SQLAlchemyVisitor(filepath, model_name)
                        visitor.visit(tree)
                    except SyntaxError as e:
                        click.echo(
                            click.style(
                                f"Syntax error in {filepath}: {e}",
                                fg="red",
                            )
                        )


if __name__ == "__main__":
    main()
