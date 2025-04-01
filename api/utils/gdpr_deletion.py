import json
from collections import defaultdict, deque
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Set, Tuple, Union

import ddtrace
import sqlalchemy.engine.result
from pymysql.constants import CLIENT
from sqlalchemy import MetaData, create_engine, delete, inspect, text
from sqlalchemy.exc import IntegrityError

import configuration
from authn.models.user import User
from authz.utils.permissions import get_permission_dictionary
from authz.utils.rbac_permissions import DELETE_GDPR_USER
from care_plans.care_plans_service import CarePlansService
from common.health_data_collection.base_api import make_hdc_request
from messaging.models.messaging import Channel
from models.enterprise import OrganizationEmployee
from models.gdpr import GDPRDeletionBackup
from models.images import Image, delete_image_file
from models.tracks import MemberTrack
from models.tracks.member_track import MemberTrackPhaseReporting
from storage.connection import db
from utils.log import logger
from utils.mono_db_attributes import MONO_DB_FK_CONSTRAINTS_DICT
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers

log = logger(__name__)

USER = "user"
IMAGE = "image"


class GDPRDeleteUser:
    """
    Class to handle GDPR user data deletion.

    Parameters
    ----------
    initiator : User
        The user initiating the data deletion.
    user : User
        The user whose data is to be deleted.

    Attributes
    ----------
    user_id : int
        The ID of the user whose data is to be deleted.
    user : User
        The user whose data is to be deleted.
    data : dict
        A dictionary containing the user's identifiable data and other information.
    metadata : MetaData
        The MetaData object used to access the user related database tables.
    """

    def __init__(self, initiator: User, user: User, requested_date: date):

        if initiator.id:
            if not GDPRDeleteUser.user_has_permission_to_delete(initiator.id):
                raise PermissionError("You don't have permission to delete a user.")

        self.user_id = user.id
        self.user = user
        self.data = {
            "identifiers": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "middle_name": user.middle_name,
                "last_name": user.last_name,
            },
            "initiator": initiator.id,
            "posts": [],
        }
        self.requested_date = requested_date
        config = configuration.get_api_config()
        engine = create_engine(
            config.common.sqlalchemy.databases.default_url,
            # pymysql backward compatibility
            connect_args={
                "binary_prefix": True,
                "client_flag": CLIENT.MULTI_STATEMENTS | CLIENT.FOUND_ROWS,
            },
        )
        self.metadata = MetaData(bind=engine)
        self.metadata.reflect()
        self.db_tables = []

    @staticmethod
    def user_has_permission_to_delete(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        permissions = get_permission_dictionary(user_id, DELETE_GDPR_USER)
        return permissions[DELETE_GDPR_USER]

    @ddtrace.tracer.wrap()
    def delete(self) -> list:
        """
        Delete the user data in compliance with GDPR.

        Returns
        -------
        list
            The deletion chain indicating the order in which rows were deleted.

        Raises
        ------
        Exception
            If an error occurs during the deletion process.
        """
        try:
            log.info(f"== Start to delete internal data for user {self.user_id}. ==")
            head = self._get_gdpr_deletion_head_table()
            id_to_delete = self.user.id if head == USER else self.user.image_id
            self._delete_user_profile_image_from_bucket()
            deletion_chain = self._delete_table(head, "id", id_to_delete, self.user_id)
            self._record_action()
            self._delete_user_from_services(self.user_id)
            log.info(f"== Deleted all data for user {self.user_id} successfully! ==")
            return deletion_chain
        except Exception as e:
            error_message = f"An error occurred when deleting {self.user_id}, {e}"
            log.error(error_message)
            raise Exception(error_message) from e

    @ddtrace.tracer.wrap()
    def _delete_user_profile_image_from_bucket(self) -> None:
        if self.user.image_id:
            image = Image.query.get_or_404(self.user.image_id)
            try:
                delete_image_file(image.storage_key)
            except Exception as e:
                log.warning(
                    f"Could not delete image_id={self.user.image_id} from GCS. Exception: {e}"
                )

    @ddtrace.tracer.wrap()
    def _get_gdpr_deletion_head_table(self) -> str:
        """
        Get the GDPR deletion chain's head table.
        https://mavenclinic.atlassian.net/browse/CPCS-1901

        In the `user` table, a foreign key `image_id` points to the `image` table. An image is deemed as a profile
        image if and only if it is exclusively linked to a single user.

        Consequently, an image will not be classified as a profile image (and hence, not as PII data), leading to the
        `user` table being identified as the head of the deletion chain, if any of the following conditions hold true:
        1. The `image_id` value is `None`
        2. There are multiple users linked to a single image

        In all other scenarios, the `image` table becomes the head of the deletion chain.
        """

        if self.user.image_id is None:
            return USER

        user_count = (
            db.session.query(User).filter(User.image_id == self.user.image_id).count()
        )
        if user_count != 1:
            return USER

        return IMAGE

    @ddtrace.tracer.wrap()
    def _delete_table(
        self,
        head_table: str,
        column: str,
        column_value: Union[int, str],
        user_id: int,
    ) -> list:
        """
        Delete the data from a specified head table and generate a deletion chain.

        Parameters
        ----------
        head_table : str
            The name of the table from which to delete data.
        column : str
            The name of the column in the head table.
        column_value : Union[int, str]
            The value in the column for the rows in head table to be deleted.
        user_id : int
            The ID of the user whose data is being deleted.

        Returns
        -------
        list
            The deletion chain indicating the order in which tables were deleted.

        Raises
        ------
        Exception
            If an error occurs during the deletion process.
        """
        try:
            deletion_chain = self._get_deletion_chain_preview(
                head_table, column, column_value
            )
            self._delete_update_data(
                deletion_chain,
                head_table,
                column,
                column_value,
                user_id,
            )
            return deletion_chain
        except Exception as e:
            err_msg = (
                f"An error occurred when deleting table {head_table} with key "
                f"{column} = {column_value}: {e}"
            )
            log.error(err_msg)
            raise Exception(err_msg)

    @ddtrace.tracer.wrap()
    def _record_action(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        audit_log_info = {
            "user_id": self.user_id,
            "action_type": self._action_type(),
            "action_target_type": "user",
            "action_target_id": self.user_id,
        }
        log.info("audit_log_events", audit_log_info=audit_log_info)
        return audit_log_info

    @ddtrace.tracer.wrap()
    def _action_type(self) -> str:
        return "GDPR delete user"

    @ddtrace.tracer.wrap()
    def _get_dependent_column(
        self,
        row: sqlalchemy.engine.result.RowProxy,
        dependent_table: str,
        referenced_table: str,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the column in a table that depends on another table and its corresponding value in a given row.

        Parameters
        ----------
        row : sqlalchemy.engine.result.RowProxy
            The row from the database query.
        dependent_table : str
            The name of the table that has a dependency.
        referenced_table : str
            The name of the table being referenced by the dependent_table.

        Returns
        -------
        dict
            A dictionary with the name of the dependent column and its corresponding value in the row.

        Raises
        ------
        Exception
            If an error occurs while retrieving the dependent column.
        """
        try:
            dependents = []
            dependent_column = "dependent_column"
            dependent_value = "dependent_value"
            # if referenced_table == "user":
            #     dependent_column = "user_id"
            #     dependent_value = row["id"]
            key = (dependent_table, referenced_table)
            if key in MONO_DB_FK_CONSTRAINTS_DICT:
                dependent_list = MONO_DB_FK_CONSTRAINTS_DICT[key]
                for dependent in dependent_list:
                    dependent_column, dependent_pk_key = dependent
                    dependent_value = row[dependent_pk_key]
                    dependents.append(
                        {"column": dependent_column, "value": dependent_value}
                    )
            return dependents
        except Exception as e:
            err_msg = f"Error in getting dependent column: {e}"
            log.error(err_msg)
            raise Exception(err_msg) from e

    @ddtrace.tracer.wrap()
    def _get_all_fk_constraints(self, inspector) -> defaultdict:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        dependent_tables = defaultdict(set)
        self.db_tables = inspector.get_table_names()
        for table_name in self.db_tables:
            for fk in inspector.get_foreign_keys(table_name):
                dependent_tables[fk["referred_table"]].add(table_name)

        # 6 legacy tables only in production
        dependent_tables["organization"].add("organization_package")
        dependent_tables["organization"].add("organization_allowed_coordinator")
        dependent_tables["practitioner_profile"].add("organization_allowed_coordinator")
        dependent_tables["practitioner_profile"].add("care_coordinator_selection")
        dependent_tables["practitioner_profile"].add("coordinator_allowed_module")
        dependent_tables["practitioner_profile"].add("featured_practitioner")
        dependent_tables["module"].add("free_module_transition")
        dependent_tables["module"].add("coordinator_allowed_module")

        # Add virtual fk constraints to link treatment_procedure to reimbursement_wallet
        dependent_tables["reimbursement_wallet"].add("treatment_procedure")
        # Add virtual fk constraints to link care_plan_activity_publish to message
        dependent_tables["message"].add("care_plan_activity_publish")

        return dependent_tables

    # Get the deletion chain
    @ddtrace.tracer.wrap()
    def _get_deletion_chain(
        self,
        head_table: str,
        column: str,
        column_value: Union[int, str],
        dependent_tables: defaultdict,
    ) -> list:
        """
        Generate the chain of rows in the database to be deleted.

        This function traverses the database schema by following foreign key constraint relationships
        and collects the rows that need to be deleted in the deletion chain list.

        Parameters
        ----------
        head_table : str
            The name of the table to start the deletion from.
        column : str
            The name of the column in the head_table where deletion will start.
        column_value : Union[int, str]
            The value in the column of the head_table that is the starting point for deletion.
        dependent_tables : defaultdict
            A dictionary that maps each table in the database to a set of tables that are
            dependent on it (tables that have a foreign key referencing it).

        Returns
        -------
        list
            The deletion chain as a list. Each item in the list is a tuple with the name of
            a table, the name of the column, and the value in the column.

        """
        visited = set()
        deletion_chain = []
        revert_deletion_chain = []
        queue = deque([(head_table, column, column_value)])

        while queue:
            table_name, column, column_value = queue.popleft()
            # the legacy tables only existing in production database
            if table_name not in self.db_tables:
                continue
            if (table_name, column, column_value) not in visited:
                visited, deletion_chain = self._visit_node(
                    visited, deletion_chain, table_name, column, column_value
                )

                revert_deletion_chain, queue = self._process_rows(
                    revert_deletion_chain,
                    queue,
                    dependent_tables,
                    deletion_chain,
                    table_name,
                    column,
                    column_value,
                )

        return revert_deletion_chain

    # Visit a node and add it to the deletion chain
    @ddtrace.tracer.wrap()
    def _visit_node(
        self,
        visited: set,
        deletion_chain: list,
        table_name: str,
        column: str,
        value: Union[int, str],
    ) -> Tuple[set, list]:
        visited.add((table_name, column, value))
        chain = self._create_dict_for_backup(table_name, column, value, {})
        deletion_chain.append(chain)
        return visited, deletion_chain

    # Process rows for a visited node
    @ddtrace.tracer.wrap()
    def _process_rows(
        self,
        revert_deletion_chain: list,
        queue: deque,
        dependent_tables: defaultdict,
        deletion_chain: list,
        table: str,
        column: str,
        column_value: Union[int, str],
    ) -> Tuple[list, deque]:
        query = text(f"SELECT * FROM {table} WHERE {column} = :pk_value")
        rows = db.session.execute(query, {"pk_value": column_value}).fetchall()
        if rows:
            revert_deletion_chain, queue = self._process_individual_rows(
                revert_deletion_chain,
                queue,
                dependent_tables,
                deletion_chain,
                rows,
                table,
            )
        return revert_deletion_chain, queue

    @ddtrace.tracer.wrap()
    def _process_individual_rows(
        self,
        revert_deletion_chain: list,
        queue: deque,
        dependent_tables: defaultdict,
        deletion_chain: list,
        rows: list,
        table: str,
    ) -> Tuple[list, deque]:
        for row in rows:
            if row:
                for column in row.keys():
                    deletion_chain[-1]["data"][column] = row[column]
                revert_deletion_chain.append(deletion_chain[-1])
                dependents = dependent_tables[table]
                for dependent_table in dependents:
                    dependent_keys: List[Dict[str, Any]] = self._get_dependent_column(
                        row, dependent_table, table
                    )
                    for dependent_key in dependent_keys:
                        queue.append(
                            (
                                dependent_table,
                                dependent_key["column"],
                                dependent_key["value"],
                            )
                        )
        return revert_deletion_chain, queue

    @ddtrace.tracer.wrap()
    def _get_deletion_chain_preview(
        self, head_table: str, column: str, column_value: Union[int, str]
    ) -> list:
        """
        Gets a preview of the deletion chain by traversing the database schema and identifying which rows will need to
        be deleted.

        Parameters
        ----------
        head_table : str
            The name of the table to start the deletion from.
        column : str
            The name of the column in the head table that contains the user's data.
        column_value : Union[int, str]
            The value in the column that corresponds to the user's data.

        Returns
        -------
        list
            A list of dictionaries representing the deletion chain preview. Each dictionary contains the table name,
            the key column, and its value.

        Raises
        ------
        Exception
            If an error occurs during the operation.
        """
        try:
            inspector = inspect(db.engine)
            dependent_tables = self._get_all_fk_constraints(inspector)
            clean_deletion_chain = self._get_deletion_chain(
                head_table, column, column_value, dependent_tables
            )
            return clean_deletion_chain

        except Exception as e:
            log.error(
                f"An error occurred when get deletion_chain_preview"
                f" table: {head_table}, key: {column}, value: {column_value}: {e.args[0]}"
            )
            raise Exception(
                f"An error occurred in _get_deletion_chain_preview"
                f"table: {head_table}, key: {column}, value: {column_value}: {e.args[0]}"
            )

    @ddtrace.tracer.wrap()
    def _delete_update_data(
        self,
        deletion_chain_in_dependency_order: list,
        head_table: str,
        column: str,
        column_value: Union[int, str],
        user_id: int,
    ) -> None:
        """
        Deletes data according to the provided deletion chain.

        Parameters
        ----------
        deletion_chain_in_dependency_order : list
            The list of tables and rows to delete, start from head table to leaf tables.
        head_table : str
            The name of the head table where the deletion begins.
        column : str
            The name of the column in the head table that contains the user's data.
        column_value : Union[int, str]
            The value in the column that corresponds to the user's data.
        user_id : int
            The ID of the user whose data is to be deleted.

        Raises
        ------
        Exception
            If an error occurs during the deletion.
        """
        try:
            # Delete in reverse order to avoid foreign key constraints
            deletion_queue = deque(reversed(deletion_chain_in_dependency_order))
            real_deletion_order = []

            original_channels = self._update_channel_table()
            real_deletion_order.extend(original_channels)

            self._delete_rows(deletion_queue, real_deletion_order)

            # Append member_track original data
            original_member_tracks, member_track_ids = self._update_member_track()
            real_deletion_order.extend(original_member_tracks)

            if member_track_ids:
                # Update member_track_phases PII
                original_member_track_phases = self._update_member_track_phase(
                    member_track_ids
                )
                real_deletion_order.extend(original_member_track_phases)

            # Append member_track original data
            (
                original_organization_employee,
                organization_employee_ids,
            ) = self._update_organization_employee()
            real_deletion_order.extend(original_organization_employee)

            real_deletion_order_json_str = self._serialize_deletion_order(
                real_deletion_order
            )

            self._backup_deletion_data(
                user_id, real_deletion_order_json_str, self.requested_date
            )

        except Exception as e:
            db.session.rollback()
            log.error(
                f"An error occurred when delete {head_table} key = {column}, "
                f"val = {column_value}: {e}"
            )
            # Raise a new exception while preserving the original traceback
            raise Exception(
                f"An error occurred when delete {head_table} key = {column}, "
                f"val = {column_value}: {e}"
            ) from e

    @ddtrace.tracer.wrap()
    def _delete_rows(self, deletion_queue: deque, real_deletion_order: list) -> None:
        """
        Deletes rows from the database according to the provided deletion queue and logs the  order of deletion.

        Parameters
        ----------
        deletion_queue : deque
            The queue of rows to delete.
        real_deletion_order : list
            The list that keeps track of the order in which rows are deleted.

        Raises
        ------
        Exception
            If an error occurs during the deletion, specifically if a dependency loop is detected.
        """
        retry_count = 0
        deletion_item_count = len(deletion_queue)
        deletion_queue_backup = deletion_queue.copy()

        while deletion_queue:
            row_info = deletion_queue.popleft()
            table = row_info["table"]
            fk_column = row_info["foreign_key"]["column"]
            fk_value = row_info["foreign_key"]["value"]

            table_class = self.metadata.tables[table]

            delete_query = delete(table_class).where(
                table_class.c[fk_column] == fk_value
            )

            try:
                db.session.execute(delete_query)
            except IntegrityError as e:
                retry_count += 1
                deletion_queue.append(row_info)
                # loop all items in the deletion_queue.
                # raise an exception to avoid infinity loop
                if retry_count == deletion_item_count:
                    log.error(
                        f"Find dependency loop in deletion chain when delete {self._serialize_deletion_order(list(deletion_queue_backup))}."
                        f"Left items in deletion_queue are: {self._serialize_deletion_order(list(deletion_queue))}"
                        f"Delete query is: {deletion_queue}"
                        f"Error msg: {e}"
                    )
                    raise Exception("Find dependency loop in deletion chain.") from e
            # no exception
            else:
                retry_count = 0
                real_deletion_order.append(row_info)
                deletion_item_count = len(deletion_queue)

    @ddtrace.tracer.wrap()
    def _serialize_deletion_order(self, real_deletion_order: list) -> str:
        return json.dumps(
            real_deletion_order,
            default=lambda x: (
                x.isoformat()
                if (isinstance(x, datetime) or isinstance(x, date))
                else None
            ),
        )

    @ddtrace.tracer.wrap()
    def _backup_deletion_data(
        self, user_id: int, deletion_data: str, requested_date: date
    ) -> None:
        new_record = GDPRDeletionBackup(
            user_id=user_id, data=deletion_data, requested_date=requested_date
        )
        db.session.add(new_record)
        db.session.commit()

    @ddtrace.tracer.wrap()
    def _update_organization_employee(self) -> Tuple[List[Any], Set[int]]:
        """
        Update organization employee object as it is flagged by legal team as KEEP.
        """
        original_organization_employees = []
        organization_employee_ids = set()

        organization_employees = (
            db.session.query(OrganizationEmployee)
            .filter(OrganizationEmployee.email == self.user.email)
            .all()
        )

        organization_employees_dicts = self._get_items_dict(organization_employees)

        for organization_employee, organization_employee_dict in zip(
            organization_employees, organization_employees_dicts
        ):
            organization_employee_ids.add(organization_employee.id)
            original_organization_employee = self._create_dict_for_backup(
                "organization_employee",
                "email",
                self.user.email,
                organization_employee_dict,
            )
            original_organization_employees.append(original_organization_employee)
            organization_employee.alegeus_id = None
            organization_employee.email = None

        return original_organization_employees, organization_employee_ids

    @ddtrace.tracer.wrap()
    def _update_member_track(self) -> Tuple[List[Any], Set[int]]:
        """
        Update member_track object as it is flagged by legal team as KEEP.
        Notice: db session only commits once, so no need to commit after the update.
        """
        original_member_tracks = []
        member_track_ids = set()

        member_tracks = (
            db.session.query(MemberTrack)
            .filter(MemberTrack.user_id == self.user_id)
            .all()
        )

        member_tracks_dicts = self._get_items_dict(member_tracks)

        for member_track, member_tracks_dict in zip(member_tracks, member_tracks_dicts):
            member_track_ids.add(member_track.id)
            original_member_track = self._create_dict_for_backup(
                "member_track", "user_id", self.user_id, member_tracks_dict
            )
            original_member_tracks.append(original_member_track)
            member_track.user_id = None
            member_track.anchor_date = None
            if member_track.active:
                log.warn("MemberTrack is still active", member_track_id=member_track.id)

        return original_member_tracks, member_track_ids

    @ddtrace.tracer.wrap()
    def _update_member_track_phase(self, member_track_ids: Set[int]) -> List[Any]:
        original_member_track_phases = []
        for id in member_track_ids:
            member_track_phases = (
                db.session.query(MemberTrackPhaseReporting)
                .filter(MemberTrackPhaseReporting.member_track_id == id)
                .all()
            )

            member_track_phase_dicts = self._get_items_dict(member_track_phases)

            for member_track_phase, member_track_phase_dict in zip(
                member_track_phases, member_track_phase_dicts
            ):
                original_member_track_phase = self._create_dict_for_backup(
                    "member_track_phase", "member_track_id", id, member_track_phase_dict
                )
                original_member_track_phases.append(original_member_track_phase)
                member_track_phase.ended_at = None

        return original_member_track_phases

    @ddtrace.tracer.wrap()
    def _delete_table_data(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, fk_ids: Set[int], model, filter_col_name, table_name: str, fk_name: str
    ) -> List[Any]:
        original_rows = []
        for id in fk_ids:
            rows = db.session.query(model).filter(filter_col_name == id).all()

            if rows:
                for row in rows:
                    row_dict = self._get_items_dict(row)
                    original_row = self._create_dict_for_backup(
                        table_name, fk_name, id, row_dict
                    )
                    original_rows.append(original_row)

                    db.session.delete(row)

        return original_rows

    @ddtrace.tracer.wrap()
    def _update_channel_table(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        channels = (
            db.session.query(Channel)
            .join(
                ReimbursementWalletUsers,
                Channel.id == ReimbursementWalletUsers.channel_id,
            )
            .filter(ReimbursementWalletUsers.user_id == self.user_id)
            .all()
        )
        original_channels = []

        for channel in channels:
            if channel and channel.name:
                channel_dict = self._get_items_dict(channel)
                original_channel = self._create_dict_for_backup(
                    "channel", "id", channel.id, channel_dict
                )
                original_channels.append(original_channel)
                channel.name = channel.name.replace(
                    self.user.first_name, "_gdpr_user_name"
                )
                channel.comment = "GDPR delete."
        return original_channels

    @ddtrace.tracer.wrap()
    def _get_items_dict(self, items):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not isinstance(items, Iterable) or isinstance(items, str):
            items = [items]

        return [
            {
                key: value
                for key, value in item.__dict__.items()
                if not key.startswith("_")
            }
            for item in items
        ]

    @ddtrace.tracer.wrap()
    def _create_dict_for_backup(
        self, table_name: str, column: str, value: Union[str, int], data: dict
    ) -> dict:
        return {
            "table": table_name,
            "foreign_key": {"column": column, "value": value},
            "data": data,
        }

    @ddtrace.tracer.wrap()
    def _delete_user_from_services(self, user_id: int) -> None:
        try:
            # Delete from Health-Data-Collection (HDC)
            make_hdc_request(
                "/-/gdpr/member-delete",
                data={"member_id": user_id},
                extra_headers={"X-Maven-User-Identities": "maven_service"},
                method="POST",
                user_internal_gateway=True,
            )
            # Delete from Care-Plans-Service (CPS)
            CarePlansService.send_gdpr_member_delete(user_id, 10)
        except Exception as e:
            log.error(
                "Error in _delete_user_from_services",
                error={"type": type(e).__name__, "message": str(e)},
                user_id=user_id,
            )
