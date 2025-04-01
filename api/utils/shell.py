import datetime
import json
from pprint import pprint

import IPython
import traitlets.config
from IPython.terminal import ipapp
from sqlalchemy import pool

import configuration
from app import create_app
from authn.models.user import User
from storage.connection import db

DEFAULT_BANNER = """

Welcome to the Maven Python REPL. This is an ipython shell with some
preconfigured goodies. They are:

From the python stdlib:
- pprint
- json
- datetime

From our application:
- api is an instance of the api flask app with test context already set
- client is a configured test client for the flask api app (you can use to
GET, POST, PUT, etc...)
- db is the database object
- User is the User ORM class

"""


class Shell(object):
    def __init__(self, extra_context=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        context = shell_context()

        if extra_context and type(extra_context) is dict:
            context.update(extra_context)

        self.context = context

    def embed(self, banner=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        banner = banner or DEFAULT_BANNER
        config: traitlets.config.Config = ipapp.load_default_config()
        config.IPCompleter.use_jedi = False
        config.TerminalInteractiveShell.colors = "linux"
        config.TerminalInteractiveShell.highlighting_style = "native"
        config.TerminalInteractiveShell.loop_runner = "sync"
        config.TerminalInteractiveShell.autoawait = False
        config.InteractiveShellEmbed = config.TerminalInteractiveShell
        IPython.embed(user_ns=self.context, banner1=banner, config=config, using=None)


def shell_context():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    app, client = get_app_and_client()
    context = dict(
        pprint=pprint,
        json=json,
        datetime=datetime,
        api=app,
        client=client,
        db=db,
        analyze_relations=analyze_relations,
        all_dependencies=all_dependencies,
        all_dependents=all_dependents,
        dependent_relations=dependent_relations,
        User=User,
    )

    return context


def get_app_and_client():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Override the default pooling configuration.
    #   Must be done BEFORE initializing the app.
    api_config = configuration.get_api_config()
    flask_config = configuration.api_config_to_flask_config(api_config)
    flask_config.SQLALCHEMY_ENGINE_OPTIONS.clear()
    flask_config.SQLALCHEMY_ENGINE_OPTIONS.update(
        poolclass=pool.NullPool, echo=api_config.common.sqlalchemy.echo
    )
    app = create_app()
    app.test_request_context().push()
    client = app.test_client()
    return app, client


def analyze_relations(table_name, pretty=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    dependents = all_dependents()[table_name]
    dependencies = all_dependencies()[table_name]
    if pretty:
        print(
            """
        {} relies on (references) the following tables:

            {}

        ... and is relied on (is referenced) by these following tables:

            {}
        """.format(
                table_name,
                ", ".join(dependencies) if dependencies else "none",
                ", ".join(dependents) if dependents else "none",
            )
        )
    else:
        return dependencies, dependents


def all_dependencies():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if hasattr(all_dependencies, "cache"):
        return all_dependencies.cache

    dependents = all_dependents()
    all_dependencies.cache = {  # type: ignore[attr-defined] # "Callable[[], Any]" has no attribute "cache"
        t: set(k for k, v in dependents.items() if t in v) for t in dependents.keys()
    }

    return all_dependencies.cache  # type: ignore[attr-defined] # "Callable[[], Any]" has no attribute "cache"


def all_dependents():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if hasattr(all_dependents, "cache"):
        return all_dependents.cache

    tt = (
        t[0]
        for t in db.session.execute(
            "select t.table_name from information_schema.tables t where table_schema = 'maven'"
        )
    )
    all_dependents.cache = {  # type: ignore[attr-defined] # "Callable[[], Any]" has no attribute "cache"
        table_name: dependent_relations(table_name) for table_name in tt
    }

    return all_dependents.cache  # type: ignore[attr-defined] # "Callable[[], Any]" has no attribute "cache"


def dependent_relations(table_name, visited=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if visited is None:
        visited = set()

    neighbors = set(
        r[0]
        for r in db.session.execute(
            """
select distinct k.table_name
from information_schema.key_column_usage k
where
    k.table_schema = 'maven'
    and k.referenced_table_name = :table_name
    and k.referenced_table_schema = 'maven'
    and k.referenced_column_name = (
        select j.column_name
        from
            information_schema.table_constraints t
            left join information_schema.key_column_usage j
            using(constraint_name,table_schema,table_name)
            where
                t.constraint_type='PRIMARY KEY'
                and t.table_schema='maven'
                and t.table_name=:table_name
            limit 1
    );
""",
            {"table_name": table_name},
        )
    )

    new_neighbors = neighbors - visited
    visited.update(new_neighbors)

    for n in new_neighbors:
        # visited is shared by reference and is used to collect the recursive union
        dependent_relations(n, visited)

    return visited
