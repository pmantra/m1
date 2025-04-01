from __future__ import annotations

import contextlib
import json
import os
import traceback
import warnings
from collections import defaultdict
from enum import Enum
from typing import Callable, Generator, List, Tuple, Type, Union

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.dialects import mysql
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Query

import storage.dev as dev
from utils.log import logger

log = logger(__name__)

"""
-----------------------------------------------------------
enable_db_performance_warnings is a test utility that can be used to identify
database interaction hot spots. It tracks all DB queries made within a scope
and call count metrics and code traces to identify the source of the query.

Additionally it provides options for 2 thresholds
warning_threshold:
    if the total number of queries exceeds this threshold, a warning will be
    printed (test will still pass)
    If not provided no warnings will be printed
failure_threshold:
    if the total number of queries exceeds this threshold, an assertion will
    be thrown (test will fail)
    If not provided no assertions will be thrown

Suggestions for use:
    Initially wrap a simple test case that calls an endpoint.
    Example:
with enable_db_performance_warnings(database=db, warning_threshold=20, failure_threshold=100):
    res = client.get(
        "/api/v1/channels",
        data={"user_ids": [member.id]},
        headers=api_helpers.json_headers(user=member),
    )
    assert res.status_code == 200
    ...

    Then review the warning logs for TOTAL SQL QUERIES. You should immediately
    set 1 higher that this value as your failure_threshold, we dont want the
    number of DB calls to increase in the future.

    Then you can set the warning_threshold to a reasonable goal value
    depending on your starting call count.

    Use the warning logs to help guide you to the hot spots and iterate on
    improvements until the DB calls count has reduced.

    Set the alert_threshold to the new lower value to ensure we dont regress
    in the future.

    Rinse and repeat :)
"""


# this represents the observed average round trip (app+net+mysql+net+app)
# duration of a query. it is used to estimate latency impact. this is not a
# precise value but should be considered the rough cost of any single query.
SQL_QUERY_BASELINE_DURATION_MS = 15

# banner of total queries made
SQL_QUERY_COUNT_BANNER_TEMPLATE = """
----------------------------------------------
TOTAL SQL QUERIES {total_queries}
in test {test_name}
----------------------------------------------
"""

# banner of total queries made with warning threshold
SQL_QUERY_COUNT_WITH_WARNING_BANNER_TEMPLATE = """
----------------------------------------------
QUERY COUNT WARNING!

Total SQL Queries: [{total_queries}]
in test {test_name}
which is above the warning threshold of [{warning_threshold}] by [{surplus_query_count}] queries.
This may increase latency by [{estimated_added_latency_ms}ms]
----------------------------------------------
"""

# roll up information about a specific query
SQL_QUERY_CALL_DETAILS_TEMPLATE = """
----------------------------------------------
This query was made [{call_count}] times

{query}

Usage traceback:
{stack_info}
----------------------------------------------
"""

# printed when a query analyzer detects a warning
SQL_QUERY_ANALYSIS_WARNING = """
----------------------------------------------
This query produced a warning during analysis

{query}

Reasoning:
{reasoning}

Query plan:
{query_plan}

Usage traceback:
{stack_info}
----------------------------------------------
"""

# printed when a query analyzer detects a critical issue
SQL_QUERY_ANALYSIS_FAILURE = """
----------------------------------------------
This query produced a critical failure during analysis

{query}

Reasoning:
{reasoning}

Query plan:
{query_plan}

Usage traceback:
{stack_info}
----------------------------------------------
"""

# printed when a query analyzer detects a critical issue
COMMIT_COUNT_FAILURE = """
----------------------------------------------
The code path under test made [{commit_count}] commits which is outside the 
defined bounds. (-1 no bound)

Upper: {commit_count_upper_bound}
Lower: {commit_count_lower_bound}

This can signal that the code under test is missing an expected commit or a
nested commit has been introduced by a dependency. Each commit closes the
current transaction and opens a new one which can include acquiring a new
connection from the pool. 

Call traces listed below (if available).

Commit count:
{commit_count}

Tracebacks:
{tracebacks}
----------------------------------------------
"""

# used to detect queries we inject
EXPLAIN_WATERMARK: str = "pytests/db_util::enable_db_performance_warnings"
# strings used during fixture load and cleanup
IGNORED_TEST_OPERATIONAL_QUERIES: List[str] = [
    "ROLLBACK",
    EXPLAIN_WATERMARK,
]


# wraps the warnings.warn function for easier use
def print_message(msg) -> None:
    warnings.warn(
        msg,
        stacklevel=2,
    )


def filter_application_paths(line: str = "") -> bool:
    """
    Filter trace lines to only include paths within the api application
    exclude paths to this file. If we fail to process the line include it in
    the trace information as a fallback.
    return True to include line, False to exclude it
    """
    try:
        first_party = all(
            s not in line
            for s in (
                __file__,
                "site-packages",
                "/bin/",
                "<lambda>",
                "<string>",
                "in wrapper",
            )
        )
        return first_party
    except Exception as e:
        print_message(f"Failed to inject query traceback {e}")
    return True


def test_keys(
    k: Union[str, None] = None,
    v: Union[dict, list, str, None] = None,
    validator: Union[Callable, None] = None,
) -> bool:
    """
    Given some nested data structure, recursively test all keys against a
    validator function. If the validator returns False, return False.
    For the root key use None.
    """
    # exit early if there is no validator given
    if validator is None:
        return True

    if not validator(k, v):
        return False

    if isinstance(v, list):
        for item in v:
            # each list item is tested against the parent key
            # For example:
            # given : "access_type": ["foo", "bar", "baz"]
            # test : "access_type": "foo"
            # test : "access_type": "bar"
            # test : "access_type": "baz"
            if not test_keys(k, item, validator):
                return False
    elif isinstance(v, dict):
        for key, item in v.items():
            if not test_keys(key, item, validator):
                return False
    return True


class QueryAnalyzerResult(Enum):
    """
    These signals are used by the QueryAnalyzer to identify the severity of the
    issue discovered with the given query
    """

    # no issue found
    PASS = 0
    # issue found, but not critical
    WARN = 1
    # issue found, critical
    FAIL = 2


class DBQueryRecord:
    """
    Holds a fully hydrated, ready to execute SQL query. During instantiation it
    also captures stack trace information relative to this applications code.
    """

    def __init__(self, statement: str):
        self.statement: str = statement
        self.stack_info: str = ""
        self.query_plan_json: dict = {}

        self.capture_stack_info()

    def capture_stack_info(self) -> None:
        """
        During instantiation capture the stack trace information
        """
        try:
            self.stack_info = "".join(
                filter(filter_application_paths, traceback.format_stack())
            )
        except Exception as e:
            print_message(f"Failed to inject query traceback {e}")

    def save_query_plan(self, plan_json) -> None:
        """
        Given a plan result, expected to be a json object save it to the record
        """
        self.query_plan_json = plan_json


class DBQueryCapture:
    """
    Custom log handler that captures log lines to an in-memory array
    Stack traces are filtered to only include application paths within `api`
    """

    def __init__(self, **kwargs):
        self.warn_no_parameters = kwargs.get("warn_no_parameters", False)
        self.queries = []

    def capture(
        self,
        database: SQLAlchemy,
        query: Query,
    ):
        """
        Captures a history of calls made to the DB during a test run.
        During a capture it also attempts to run EXPLAIN on the query and
        capture the resulting plan.
        """
        # omit queries that we generate or operational queries used during
        # seeding and error handling. Exits early if any string in
        # IGNORED_TEST_OPERATIONAL_QUERIES appears in the query.
        compiled = query.compile(dialect=mysql.dialect())
        stmt_str = str(compiled)
        if any(sentinel in stmt_str for sentinel in IGNORED_TEST_OPERATIONAL_QUERIES):
            return

        # instantiate the query record
        record = DBQueryRecord(
            statement=stmt_str,
        )

        # if there are no params, NULLs will appear in the query plan producing
        # false positives of access_type: "ALL" which looks like a table scan.
        # Additionally if required query args are None, Explain compilation
        # will fail.
        if any(value is not None for value in compiled.params.values()):
            try:
                explain_json = dev.analyze(
                    database=database,
                    query=query,
                    as_json=True,
                    watermark=EXPLAIN_WATERMARK,
                )
                record.save_query_plan(explain_json)
            except Exception as e:
                print_message(
                    f"Failed to capture query plan \n\nError:\n{e}\n\nQuery:\n{stmt_str}"
                )
        else:
            if self.warn_no_parameters:
                print_message(f"query had no params {compiled.params}\n{stmt_str}")
        # save the query record for later analysis
        self.queries.append(record)


class QueryAnalyzer:
    """
    Base class for query analyzers. Subclass this to implement custom analysis
    """

    def __init__(self, query_record: DBQueryRecord):
        self.query_record = query_record

    def reasoning(self):
        raise NotImplementedError()

    def analyze_query(self, database: SQLAlchemy) -> QueryAnalyzerResult:
        raise NotImplementedError()


class DisallowTableScan(QueryAnalyzer):
    """
    Analyzer that detects table scans in query plans. It detects when
    access_type is set to "ALL" or "INDEX" in the query plan that do not resolve
    to the usage of a table index. This is a common cause of full table scans.
    See docs/sql/access-type.md for more information.
    """

    def reasoning(self) -> str:
        return "Use of access_type INDEX or ALL found with out index resolution. Please see docs/sql/access-type.md for more information."

    def test_access_type(self, access_type: str) -> bool:
        def validator(k: str, v: str) -> bool:
            try:
                if k == "table" and isinstance(v, dict):
                    at = v.get("access_type")
                    matches_access_type = (
                        at is not None and at.lower() == access_type.lower()
                    )
                    # technically used_index should always be true when used_index_name
                    # is present but just to be sure we will look for either
                    used_index_name = v.get("key")
                    used_index = v.get("using_index") is True

                    # For now we are accepting ALL over materialized subqueries
                    # because they are `assumed` to present a substantially
                    # smaller row set for processing. If that subquery does not
                    # utilize an index the parent query will still fail.
                    was_materialized_from_subquery = (
                        v.get("materialized_from_subquery") is not None
                    )

                    # if an index was available but not used this likely
                    # indicates that the optimizer decided a scan to be more
                    # performant given the table size. For now we are going to
                    # mark this as an acceptable case. If we find this to be a
                    # problem we can adjust.
                    possible_keys = v.get("possible_keys")
                    index_was_available = (
                        possible_keys is not None and len(possible_keys) > 0
                    )

                    # if this is the access_type we are looking for an an index
                    # was not used this is a failure. We make a special
                    # consideration for materialized subqueries as they are
                    # assumed to be small enough to not require an index.
                    if matches_access_type:
                        if (
                            not used_index
                            and used_index_name is None
                            and not was_materialized_from_subquery
                            and not index_was_available
                        ):
                            return False

            except Exception as e:
                print("Failed running test_access_type validator", e)
            return True

        return test_keys(v=self.query_record.query_plan_json, validator=validator)

    def analyze_query(self, database: SQLAlchemy) -> QueryAnalyzerResult:
        # we are not able to perform an index usage analysis without a query plan
        if self.query_record.query_plan_json is None:
            return QueryAnalyzerResult.PASS

        try:
            if not self.test_access_type("index") or not self.test_access_type("all"):
                return QueryAnalyzerResult.FAIL
            return QueryAnalyzerResult.PASS
        except Exception as e:
            print_message(f"Failed to analyze query plan {e}")
            return QueryAnalyzerResult.WARN


class CommitTracebackCapture:
    call_count: int = 0
    traceback_list: list[str] = []

    def capture_traceback(self):
        """
        Capture the traceback of the current call stack
        """
        self.call_count += 1
        formatted_traceback = "".join(
            filter(filter_application_paths, traceback.format_stack())
        )
        self.traceback_list.append(formatted_traceback)

    def exceeds_commit_count_bounds(
        self,
        commit_count_lower_bound: int,
        commit_count_upper_bound: int,
    ) -> bool:
        return (
            commit_count_upper_bound > -1  # -1 is no upper bound
            and self.call_count > commit_count_upper_bound
        ) or (
            commit_count_lower_bound > -1  # -1 is no lower bound
            and self.call_count < commit_count_lower_bound
        )


@contextlib.contextmanager
def enable_db_performance_warnings(
    database: SQLAlchemy,
    warning_threshold: int = 0,
    failure_threshold: int = 0,
    query_analyzers: Tuple[()] | Tuple[Type[QueryAnalyzer]] = (DisallowTableScan,),
    warn_no_parameters: bool = False,
    # db.session.commit() must appear at least this many times
    # -1 means no lower bound
    commit_count_lower_bound: int = -1,
    # db.session.commit() must appear no more than this many times
    # -1 means no upper bound
    commit_count_upper_bound: int = -1,
) -> Generator:
    """
    Context manager that captures all DB queries made within the scope and
    provides analysis and warnings about the queries made.
    """
    db_call_capture = DBQueryCapture(
        warn_no_parameters=warn_no_parameters,
    )

    @event.listens_for(Engine, "before_execute")
    def receive_before_execute(conn, clauseelement, multiparams, params):
        try:
            db_call_capture.capture(
                database=database,
                query=clauseelement,
            )
        except Exception as e:
            print("Failed to capture query for analysis", e, str(clauseelement))

    # capture any assertion failures and re-raise them after logging
    encountered_exception = None

    yield  # executes the code under test

    # always clean up the listener so future tests dont get bogged down
    event.remove(Engine, "before_execute", receive_before_execute)

    match_map: dict[str, int] = defaultdict(int)
    query_log_lookup: dict[str, DBQueryRecord] = {}
    # %r appears as a side effect of the sqlalchemy query construction
    # but is not relevant to our analysis
    ignored_queries = ["%r"]
    total_queries = 0
    # group identical queries
    for query_made in db_call_capture.queries:
        if query_made.statement in ignored_queries:
            continue
        # todo: refactor this to use collections.Counter()
        match_map[query_made.statement] += 1
        query_log_lookup[query_made.statement] = query_made
        total_queries += 1
    # inverse sort by call count
    match_map = {
        k: v
        for k, v in sorted(match_map.items(), key=lambda item: item[1], reverse=True)
    }

    # analyze queries and optionally assert or warn
    for _, query_record in query_log_lookup.items():
        for analyzer in query_analyzers:
            q_analyzer = analyzer(query_record)
            analyze_result = q_analyzer.analyze_query(database)
            if analyze_result is None or analyze_result == QueryAnalyzerResult.PASS:
                continue
            elif analyze_result is QueryAnalyzerResult.WARN:
                print_message(
                    SQL_QUERY_ANALYSIS_WARNING.format(
                        query=query_record.statement,
                        reasoning=q_analyzer.reasoning(),
                        query_plan=json.dumps(query_record.query_plan_json, indent=2),
                        stack_info=query_record.stack_info,
                    )
                )
            elif analyze_result is QueryAnalyzerResult.FAIL:
                # hard fail this test with the analyzer reasoning
                message_body = SQL_QUERY_ANALYSIS_FAILURE.format(
                    query=query_record.statement,
                    reasoning=q_analyzer.reasoning(),
                    query_plan=json.dumps(query_record.query_plan_json, indent=2),
                    stack_info=query_record.stack_info,
                )
                raise AssertionError(f"DB query pattern not allowed.\n{message_body}")

    # determine outcome
    should_warn = warning_threshold > 0 and total_queries >= warning_threshold
    should_fail = failure_threshold > 0 and total_queries >= failure_threshold

    # print warnings if configured to do so
    if should_warn or should_fail:
        # pytests sets this env with the current test name
        # https://docs.pytest.org/en/7.1.x/example/simple.html#pytest-current-test-environment-variable
        test_name = (os.environ.get("PYTEST_CURRENT_TEST") or "").split(" ")[0]

        output_sections = []

        # spacer
        output_sections.extend(
            [
                "\n",
                "----------------------------------------------",
                "----------------------------------------------",
            ]
        )

        # estimate latency impact
        surplus_query_count = total_queries - warning_threshold
        estimated_added_latency_ms = (
            surplus_query_count * SQL_QUERY_BASELINE_DURATION_MS
        )

        # warning banner
        output_sections.append(
            SQL_QUERY_COUNT_WITH_WARNING_BANNER_TEMPLATE.format(
                total_queries=total_queries,
                test_name=test_name,
                warning_threshold=warning_threshold,
                surplus_query_count=surplus_query_count,
                estimated_added_latency_ms=estimated_added_latency_ms,
            )
        )

        # print queries
        for query, call_count in match_map.items():
            output_sections.append(
                SQL_QUERY_CALL_DETAILS_TEMPLATE.format(
                    call_count=call_count,
                    query=query,
                    stack_info=query_log_lookup[query].stack_info,
                )
            )

        # Also include the query count at the bottom of the warn output so its
        # easier to find when iterating on tests
        output_sections.append(
            SQL_QUERY_COUNT_BANNER_TEMPLATE.format(
                total_queries=total_queries,
                test_name=test_name,
            )
        )

        print_message("\n".join(output_sections))

    # this is sourced above. if the child call throws an exception, we want to
    # proactively bubble it ato be addressed first
    if encountered_exception is not None:
        raise encountered_exception
    # ensure the child exception is raised before our query exception to ensure
    # we are not hiding application errors
    assert (
        not should_fail
    ), f"Too many db queries! Failure threshold: {failure_threshold} Actual: {total_queries}"
