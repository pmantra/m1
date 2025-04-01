import json
from collections import defaultdict, deque
from typing import List, Optional

import ddtrace
import sqlalchemy
from sqlalchemy import MetaData, orm
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import scoped_session

from authn.errors.idp.client_error import IdentityClientError
from authn.services.integrations.idp import ManagementClient
from models.gdpr import GDPRDeletionBackup
from storage import connection
from utils.log import logger

log = logger(__name__)


class TableNotPresentInMetaDataError(Exception):
    message = "Couldn't find table in db metadata. Please check if table is present, it might be possibly deleted"

    def __init__(self) -> None:
        super().__init__(self.message)


class GDPRBackUpDataException(Exception):
    def __init__(self, message, status_code=None, payload=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        Exception.__init__(self)
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self) -> dict:
        value = dict(self.payload or ())
        value["message"] = self.message
        return value


class GDPRDataRestore:
    meta_data = None

    def __init__(self, session: orm.scoping.ScopedSession = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.scoped = session or connection.db.session
        self.pending_data_and_errors = {}
        self.duplicate_entry_rows = {}
        self.foreign_key_failure = {}

    @property
    def session(self) -> sqlalchemy.orm.Session:
        return self.scoped().using_bind("default")

    @ddtrace.tracer.wrap()
    def _deserialize_deletion_order(self, serialized_backup_data) -> List[dict]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        return json.loads(serialized_backup_data)

    def get_deletion_backup(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if user_id is None:
            return None
        gdpr_back_record = (
            self.session.query(GDPRDeletionBackup)
            .filter(GDPRDeletionBackup.user_id == user_id)
            .one_or_none()
        )
        return gdpr_back_record

    def get_data_from_deletion_backup(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        gdpr_back_record = self.get_deletion_backup(user_id)
        return (
            self._deserialize_deletion_order(gdpr_back_record.data)
            if gdpr_back_record
            else None
        )

    def upsert_records(self, backups_, metadata):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        backup_queue = deque(backups_)
        item_count = len(backup_queue)
        retry_count = 0
        while backup_queue:
            backup = backup_queue.pop()
            table_name = backup["table"]
            table = metadata.tables.get(table_name)
            filtered_names = {col.name for col in metadata.tables[table_name].columns}
            # just add columns that are present in current table schema
            data = [
                {key: row[key] for key in row.keys() & filtered_names}
                for row in backup["data"]
            ]
            insert_stmt = insert(table).values(data)
            on_conflict_keys = {
                k: getattr(insert_stmt.inserted, k) for k in filtered_names
            }
            stmt = insert_stmt.on_duplicate_key_update(**on_conflict_keys)
            try:
                self.session.execute(stmt)
            except Exception as e:
                if retry_count >= item_count + 1:
                    self.add_to_pending_tables_and_errors(table_name, e, backup)
                    retry_count = 0
                else:
                    retry_count += 1
                    backup_queue.appendleft(backup)
                    log.error(f"Error in GDPR backup restoration: {e}")
            else:
                retry_count = 0
                item_count = len(backup_queue)

    def add_to_pending_tables_and_errors(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, table_name, err, backup, duplicate=False
    ):
        def add_to_dictionary(dictionary):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            if table_name in dictionary:
                dictionary[table_name]["errors"].append(err.__str__())
                dictionary[table_name]["data"].append(backup)
                dictionary[table_name]["table_in_backup"] = False
            else:
                dictionary[table_name] = {
                    "errors": [err.__str__()],
                    "data": [backup],
                    "table_in_backup": False,
                }

        add_to_dictionary(self.pending_data_and_errors)

        if duplicate:
            add_to_dictionary(self.duplicate_entry_rows)

    def prepare_data(self, backups, metadata):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        backups_ = []
        for backup in backups:
            if not backup["data"]:
                continue

            # make the data structure consistent
            if type(backup["data"]) is not list:
                backup["data"] = [backup["data"]]

            # remove the ones that are not present in metadata
            table_name = backup["table"]
            if table_name not in metadata.tables:
                self.add_to_pending_tables_and_errors(
                    table_name, TableNotPresentInMetaDataError(), backup
                )
                continue

            # serialize the string columns if they are not
            backup["data"] = self.serialize_string_columns(
                backup["table"], backup["data"], metadata
            )
            backups_.append(backup)

        backups_ = self.de_duplicate(backups_, metadata)
        return backups_

    def update_for_debugging(self, backups, metadata):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        all_tables = {backup["table"] for backup in backups}
        foreign_key_info = self.get_foreignkey_info(metadata)
        for table in self.pending_data_and_errors:
            error_msg = " ".join(self.pending_data_and_errors[table]["errors"])
            if "foreign key constraint" in error_msg:
                for key in foreign_key_info[table]:
                    if key in error_msg and key in all_tables:
                        self.pending_data_and_errors[table]["table_in_backup"] = True
                        self.foreign_key_failure[table] = key
                        break

    def restore_data(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        backups = self.get_data_from_deletion_backup(user_id)
        if not backups:
            return False
        meta_data = MetaData(bind=self.session.get_bind().engine, reflect=True)
        backups = self.prepare_data(backups, meta_data)
        self.upsert_records(backups, meta_data)
        self.update_for_debugging(backups, meta_data)

        # the commented code below can expose user related info if we have pymysql error, so should be used only
        # locally
        # filtered_info = {key: value["errors"] for key, value in self.pending_data_and_errors.items()}
        # log.error(f"some of the data wasn't restored due to errors. Details: {filtered_info}")

        if self.pending_data_and_errors:
            self.session.rollback()
            self.update_gdpr_backup(user_id)
            return False
        else:
            self.session.commit()
            return True

    @staticmethod
    def get_foreignkey_info(metadata):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        foreign_key_info = {}
        for table_name, table in metadata.tables.items():
            for foreign_key in table.foreign_key_constraints:
                referenced_table_name = foreign_key.referred_table.name

                if table_name not in foreign_key_info:
                    foreign_key_info[table_name] = {}

                if referenced_table_name not in foreign_key_info[table_name]:
                    foreign_key_info[table_name][referenced_table_name] = []
                foreign_key_info[table_name][referenced_table_name].extend(
                    foreign_key.column_keys
                )
        return foreign_key_info

    @staticmethod
    def write_to_json(file_name, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with open(file_name, "w") as file:
            json.dump(obj, file)

    @staticmethod
    def get_data_dict_by_table(data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return {d["table"]: d["data"] for d in data}

    @staticmethod
    def serialize_string_columns(table_name, data, metadata):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        We read the tables by reflecting the metadata from the actual db as opposed to the orm.
        this leads to skipping custom definitions for columns like JSON types: JSONEncodedObj.
        We need to serialize these as they are passed as arguments for table operations (insert and delete)
        So they won't be able to take advantage of auto serialization as defined in that type.
        """
        column_types = {
            col.name: col.type.__class__.__name__
            for col in metadata.tables.get(table_name).columns
        }

        serialized_data = []
        for d in data:
            for col_name, col_value in d.items():
                col_type = column_types.get(col_name, None)
                try:
                    if (
                        col_type is not None
                        and col_type.upper() in ("STRING", "TEXT", "VARCHAR", "CHAR")
                        and type(col_value) is not str
                    ):
                        serialized_value = json.dumps(col_value)
                        d[col_name] = serialized_value
                except Exception as e:
                    log.error(f"Error with serializing strings in for backup data, {e}")
            serialized_data.append(d)
        return serialized_data

    @staticmethod
    def sort_based_on_metadata(metadata, data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        sort_order = {
            value: index for index, value in enumerate(metadata.sorted_tables)
        }
        data.sort(key=lambda d: sort_order.get(d["table"], -1))
        return data

    def de_duplicate(self, backups, metadata):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        table_data = defaultdict(list)
        for backup in backups:
            table_name = backup["table"]
            if table_name not in metadata.tables:
                self.add_to_pending_tables_and_errors(
                    table_name, TableNotPresentInMetaDataError(), backup
                )
                continue
            table_data[table_name].append(backup)

        # Deduplicate data within each group
        deduplicated_backups = []
        for table_name, data_group in table_data.items():
            primary_key_columns = [
                col.name for col in metadata.tables.get(table_name).primary_key
            ]
            seen_data = set()
            deduplicated_group = []

            for backup in data_group:
                unique_data = []
                for data_entry in backup["data"]:
                    data_key = json.dumps(
                        {
                            k: v
                            for k, v in data_entry.items()
                            if k in primary_key_columns
                        },
                        sort_keys=True,
                    )
                    if data_key not in seen_data:
                        seen_data.add(data_key)
                        unique_data.append(data_entry)
                if unique_data:
                    backup_copy = backup.copy()
                    backup_copy["data"] = unique_data
                    deduplicated_group.append(backup_copy)

            deduplicated_backups.extend(deduplicated_group)

        return deduplicated_backups

    def update_gdpr_backup(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        gdpr_record = self.get_deletion_backup(user_id)
        if gdpr_record:
            gdpr_record.restoration_errors = json.dumps(self.pending_data_and_errors)
            self.session.commit()


class GDPRDataDelete:
    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, session: Optional[scoped_session] = None, management_client=None
    ):
        self.scoped = session or connection.db.session
        self.management_client = management_client or ManagementClient()

    @property
    def session(self) -> sqlalchemy.orm.Session:
        return self.scoped().using_bind("default")

    @ddtrace.tracer.wrap()
    def _validate_user_id(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if user_id is None:
            log.error("User ID is None.")
            raise ValueError("'user_id' cannot be None.")

    @ddtrace.tracer.wrap()
    def _get_external_ids(self, user_id: int) -> [str]:  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type
        restore = GDPRDataRestore()
        backups = restore.get_data_from_deletion_backup(user_id)
        external_ids = []
        for backup in backups:
            if not backup["data"]:
                continue
            if (
                backup["table"] == "user_auth"
                and "external_id" in backup["data"]
                and backup["data"]["external_id"]
            ):
                external_ids.append(backup["data"]["external_id"])
        return external_ids

    @ddtrace.tracer.wrap()
    def _delete_auth0_user(self, user_id: int, external_ids: [str]) -> bool:  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type
        failed_deletions = []

        for external_id in external_ids:
            try:
                if self.management_client.get_user(external_id=external_id):
                    self.management_client.delete_user(external_id=external_id)
                    log.info(
                        f"Delete Auth0 user {user_id} with external_id = {external_id} successfully!"
                    )
                else:
                    log.warning(
                        f"Cannot find Auth0 user {user_id} with external_id = {external_id}!"
                    )
            except IdentityClientError as e:
                log.error(
                    f"Failed to delete Auth0 user {user_id} with external_id = {external_id}: {e}"
                )
                failed_deletions.append(external_id)

        if failed_deletions:
            raise GDPRBackUpDataException(
                f"Failed to delete Auth0 users with external IDs: {', '.join(failed_deletions)}!",
                status_code=500,
            )

        return True

    @ddtrace.tracer.wrap()
    def delete(self, user_id) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self._validate_user_id(user_id)
        try:
            external_ids = self._get_external_ids(user_id=user_id)
            if not external_ids:
                log.warning("User does NOT have external_id", user_id=user_id)
            self._delete_auth0_user(user_id=user_id, external_ids=external_ids)
            log.info("Delete auth0 user data successfully!", user_id=user_id)
        except Exception as e:
            log.error(f"An error occurred during the deletion process: {e}")
            raise
