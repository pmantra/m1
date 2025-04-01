import sys
from collections import defaultdict, namedtuple
from collections.abc import Iterator
from dataclasses import dataclass, field
from sqlite3 import Binary

from testmon.common import drop_patch_version, get_system_packages
from testmon.db import DB
from testmon.process_code import checksums_to_blob
from testmon.testmon_core import SourceTree

TestExecutionId = int
FileFPId = int
FileFPKey = namedtuple("FileFPKey", ["filename", "method_checksums", "fsha"])
TestExecutionKey = namedtuple("TestExecutionKey", ["test_name"])


@dataclass
class MergedLookupTables:
    """A shared in-memory representation of file_fp and test_execution records for multiple input DBs."""

    file_fp: dict[FileFPKey, FileFPId] = field(default_factory=dict)
    test_execution: dict[TestExecutionKey, TestExecutionId] = field(
        default_factory=dict
    )

    def merge_file_fp(self, key: FileFPKey) -> FileFPId:
        return self.file_fp.setdefault(key, len(self.file_fp) + 1)

    def merge_test_execution(self, key: TestExecutionKey) -> TestExecutionId:
        return self.test_execution.setdefault(key, len(self.test_execution) + 1)


@dataclass
class InputDB:
    """TIA data from one parallel test job, mapped to merged lookup tables."""

    datafile: str
    environment_name: str
    lookup: MergedLookupTables
    db: DB = field(init=False)
    environment_id: int = field(init=False)
    system_packages: str = field(init=False)
    python_version: str = field(init=False)
    file_fp_mapping: dict[FileFPId, FileFPId] = field(default_factory=dict)
    test_execution_mapping: dict[TestExecutionId, TestExecutionId] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.db = DB(self.datafile, readonly=True)
        self._fetch_environment()
        self._set_test_execution_mapping()
        self._set_file_fp_mapping()

    def _fetch_environment(self) -> None:
        with self.db.con as con:
            con.execute("BEGIN IMMEDIATE TRANSACTION")
            cursor = con.cursor()
            environment = cursor.execute(
                """
                SELECT
                id, system_packages, python_version
                FROM environment
                WHERE environment_name = ?
                """,
                (self.environment_name,),
            ).fetchone()
            if environment is None:
                raise ValueError(
                    f"Environment '{self.environment_name}' not defined in input datafile '{self.datafile}'"
                )
            self.environment_id = environment["id"]
            self.system_packages = environment["system_packages"]
            self.python_version = environment["python_version"]

    def _set_test_execution_mapping(self) -> None:
        with self.db.con as con:
            con.execute("BEGIN IMMEDIATE TRANSACTION")
            cursor = con.cursor()
            for row in cursor.execute(
                """
                SELECT
                id, test_name
                FROM test_execution
                WHERE environment_id = ?
                """,
                (self.environment_id,),
            ):
                input_id = row["id"]
                key = TestExecutionKey(
                    test_name=row["test_name"],
                )
                merged_id = self.lookup.merge_test_execution(key)
                self.test_execution_mapping[input_id] = merged_id

    def _set_file_fp_mapping(self) -> None:
        with self.db.con as con:
            con.execute("BEGIN IMMEDIATE TRANSACTION")
            cursor = con.cursor()
            for row in cursor.execute(
                """
                SELECT
                id, filename, method_checksums, fsha
                FROM file_fp
                """,
            ):
                input_id = row["id"]
                key = FileFPKey(
                    filename=row["filename"],
                    method_checksums=row["method_checksums"],
                    fsha=row["fsha"],
                )
                merged_id = self.lookup.merge_file_fp(key)
                self.file_fp_mapping[input_id] = merged_id

    def get_execution_file_fp(self) -> Iterator[tuple[TestExecutionId, FileFPId]]:
        with self.db.con as con:
            con.execute("BEGIN IMMEDIATE TRANSACTION")
            cursor = con.cursor()
            for row in cursor.execute(
                """
                SELECT
                test_execution_id, fingerprint_id
                FROM test_execution_file_fp
                """,
            ):
                input_test_execution_id = row["test_execution_id"]
                try:
                    merged_test_execution_id = self.test_execution_mapping[
                        input_test_execution_id
                    ]
                except KeyError:
                    continue  # omit test executions filtered out for other environments
                input_file_fp_id = row["fingerprint_id"]
                merged_file_fp_id = self.file_fp_mapping[input_file_fp_id]
                yield merged_test_execution_id, merged_file_fp_id


@dataclass
class MergedDB:
    """Combined TIA data gathered from a list of input DBs and merged lookup tables."""

    datafile: str
    lookup: MergedLookupTables
    input_dbs: list[InputDB]
    source_tree: SourceTree
    db: DB = field(init=False)

    def __post_init__(self) -> None:
        self.db = DB(self.datafile, readonly=False)

    def merge(self) -> None:
        self._assert_same_environment()
        with self.db.con as con:
            con.execute("BEGIN IMMEDIATE TRANSACTION")
            cursor = con.cursor()
            db0 = self.input_dbs[0]
            cursor.execute(
                """
                INSERT INTO environment(id, environment_name, system_packages, python_version) VALUES(1, ?, ?, ?)
                """,
                (db0.environment_name, db0.system_packages, db0.python_version),
            )
            cursor.executemany(
                """
                INSERT INTO test_execution(id, test_name, environment_id) VALUES(?, ?, 1)
                """,
                [(v, k.test_name) for k, v in self.lookup.test_execution.items()],
            )

            def _file_fp_hashes(key: FileFPKey) -> tuple[Binary, str]:
                if key.fsha is not None:
                    return (key.method_checksums, key.fsha)
                module = self.source_tree.get_file(key.filename)
                method_checksums = checksums_to_blob(module.method_checksums)
                fsha = module.fs_fsha
                return method_checksums, fsha

            cursor.executemany(
                """
                INSERT INTO file_fp(id, filename, method_checksums, fsha) VALUES(?, ?, ?, ?)
                """,
                [
                    (v, k.filename) + _file_fp_hashes(k)
                    for k, v in self.lookup.file_fp.items()
                ],
            )
            cursor.executemany(
                """
                INSERT INTO test_execution_file_fp(test_execution_id, fingerprint_id) VALUES(?, ?)
                """,
                [
                    idid
                    for input_db in self.input_dbs
                    for idid in input_db.get_execution_file_fp()
                ],
            )

    def _assert_same_environment(self) -> None:
        envs = defaultdict(list)
        for db in self.input_dbs:
            k = (db.system_packages, db.python_version)
            envs[k].append(db.datafile)
        if len(envs) != 1:
            raise ValueError(
                f"Environment '{db.environment_name}' cannot be merged since it has changed across input data files: {envs}"
            )


def merge(
    input_datafiles: list[str],
    output_datafile: str,
    environment_name: str,
    rootdir: str,
) -> None:
    lookup = MergedLookupTables()
    input_dbs = [
        InputDB(datafile=f, environment_name=environment_name, lookup=lookup)
        for f in input_datafiles
    ]
    source_tree = SourceTree(rootdir=rootdir)
    merged_db = MergedDB(
        datafile=output_datafile,
        input_dbs=input_dbs,
        lookup=lookup,
        source_tree=source_tree,
    )
    merged_db.merge()


def normalize_environment(datafile: str, environment_name: str = "default") -> None:
    system_packages = drop_patch_version(get_system_packages())
    python_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    db = DB(datafile)
    with db.con as con:
        con.execute("BEGIN IMMEDIATE TRANSACTION")
        cursor = con.cursor()
        cursor.execute(
            """
            UPDATE environment SET system_packages=?, python_version=? WHERE environment_name = ?;
            """,
            (
                system_packages,
                python_version,
                environment_name,
            ),
        )
