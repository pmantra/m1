from __future__ import annotations

import csv
import datetime
import enum
import io
import json
from typing import Dict, List, TextIO

import ddtrace

from audit_log.utils import emit_audit_log_create, emit_audit_log_delete
from authn.models.user import User
from care_advocates.models.transitions import (
    CareAdvocateMemberTransitionLog,
    CareAdvocateMemberTransitionResponse,
)
from care_advocates.repository.transition_log import (
    CareAdvocateMemberTransitionLogRepository,
)
from care_advocates.services.transition_template import (
    CareAdvocateMemberTransitionTemplateService,
)
from storage.unit_of_work import SQLAlchemyUnitOfWork
from utils.log import logger

__all__ = ("CareAdvocateMemberTransitionLogService",)

log = logger(__name__)


class CareAdvocateMemberTransitionLogServiceMessage(str):
    COULD_NOT_FIND_TRANSITION_LOG = "Could not find transition log for given ID"
    CAN_NOT_DELETE_COMPLETED_TRANSITION_LOG = (
        "Can not delete an already completed CareAdvocateMemberTransitionLog"
    )
    TRANSITION_LOG_DELETED = "CA-Member Transition Log deleted"
    ERROR_DELETING_TRANSITION_LOG = (
        "Error when deleting CareAdvocateMemberTransitionLog"
    )
    NOT_IN_CSV_FORMAT = (
        "File does not appear to be in the csv format or invalid encoding"
    )
    FILE_ATTRIBUTE_ERROR = "File Attribute error, it may not be a csv file"
    NO_TRANSITIONS_FOUND = "No transitions found in the csv file"


CA_TRANSITIONS_CSV_HEADERS = ["member_id", "old_cx_id", "new_cx_id", "messaging"]


class CareAdvocateMemberTransitionLogService:
    @staticmethod
    def uow() -> SQLAlchemyUnitOfWork[CareAdvocateMemberTransitionLogRepository]:
        return SQLAlchemyUnitOfWork(CareAdvocateMemberTransitionLogRepository)

    @ddtrace.tracer.wrap()
    def get_transition_logs_data(
        self, sort_column: str = "date_transition"
    ) -> List[Dict]:

        with self.uow() as uow:
            transition_logs = uow.get_repo(
                CareAdvocateMemberTransitionLogRepository
            ).all(sort_column)

            transition_logs_data = [
                {
                    "id": tl.id,
                    "user_id": tl.user_id,
                    "user_name": tl.user.full_name,  # full_name should be obtained from practitioner_profile in the future, but data is not fully migrated from the user table yet
                    "date_uploaded": tl.created_at,
                    "date_of_transition": tl.date_transition,
                    "uploaded_file": tl.uploaded_filename,
                    "canDelete": False if tl.date_completed else True,
                    "rowProps": {"style": {"fontWeight": "bold"}}
                    if not tl.date_completed
                    else {},
                }
                for tl in transition_logs
            ]
            return transition_logs_data

    @ddtrace.tracer.wrap()
    def delete_transition_log(self, id: int) -> None:
        with self.uow() as uow:
            care_advocate_member_transition_log_repository = uow.get_repo(
                CareAdvocateMemberTransitionLogRepository
            )

            transition_log = care_advocate_member_transition_log_repository.get(id=id)
            if not transition_log:
                error_msg = (
                    CareAdvocateMemberTransitionLogServiceMessage.COULD_NOT_FIND_TRANSITION_LOG
                )
                log.info(error_msg, transition_log_id=id)
                raise IncorrectTransitionLogIDError(error_msg)
            if transition_log.date_completed is not None:
                error_msg = (
                    CareAdvocateMemberTransitionLogServiceMessage.CAN_NOT_DELETE_COMPLETED_TRANSITION_LOG
                )
                log.info(error_msg, transition_log_id=id)
                raise AlreadyCompletedTransitionError(error_msg)

            n_rows_affected = care_advocate_member_transition_log_repository.delete(
                id=id
            )
            if n_rows_affected:
                log.info(
                    CareAdvocateMemberTransitionLogServiceMessage.TRANSITION_LOG_DELETED,
                    transition_log_id=id,
                )
                uow.commit()
                emit_audit_log_delete(transition_log)
                return
            else:
                error_msg = (
                    CareAdvocateMemberTransitionLogServiceMessage.ERROR_DELETING_TRANSITION_LOG
                )
                log.warn(error_msg, transition_log_id=id)
                raise DeletingTransitionLogError(error_msg)

    @ddtrace.tracer.wrap()
    def download_transition_log_csv(self, id: int) -> tuple[str, str]:
        """Returns csv content and csv file name"""

        with self.uow() as uow:
            transition_log = uow.get_repo(
                CareAdvocateMemberTransitionLogRepository
            ).get(id=id)

            if not transition_log:
                error_msg = (
                    CareAdvocateMemberTransitionLogServiceMessage.COULD_NOT_FIND_TRANSITION_LOG
                )
                log.info(error_msg, transition_log_id=id)
                raise IncorrectTransitionLogIDError(error_msg)

            uploaded_content = json.loads(transition_log.uploaded_content)

            # Transform uploaded_content to a list of strings
            csv_lines = []
            field_names = ",".join(list(uploaded_content[0].keys()))
            csv_lines.append(field_names)

            for content_line_dict in uploaded_content:
                content_line = ",".join(map(str, content_line_dict.values()))
                csv_lines.append(content_line)

            csv_lines_str = "\n".join(csv_lines)

            return csv_lines_str, transition_log.uploaded_filename

    def _transition_error_str(self, error: str, row: List) -> str:
        if isinstance(row, Dict):
            return f"{error}: {list(row.values())}"
        else:
            return f"{error}: {str(row)}"

    def _convert_transitions_json(self, transitions: List[List]) -> Dict:
        transitions_json = []

        for member_id, old_cx_id, new_cx_id, messaging in transitions:
            transitions_json.append(
                {
                    "member_id": member_id,
                    "old_cx_id": old_cx_id,
                    "new_cx_id": new_cx_id,
                    "messaging": messaging,
                }
            )

        return transitions_json  # type: ignore[return-value] # Incompatible return value type (got "List[Dict[str, Any]]", expected "Dict[Any, Any]")

    @ddtrace.tracer.wrap()
    def _parse_transitions_data_from_csv(self, transitions_csv: TextIO) -> List[List]:

        # TODO: It may be worthwhile to break out the CSV operations into their own class
        # which the Service can use as a component. This will let us test the CSV operations in isolation,
        # then allow the Service object to be a coordinator between the repository, UOW, and CSV component.
        transitions = []
        errors = []

        try:
            with io.StringIO(transitions_csv.stream.read().decode()) as stream:  # type: ignore[attr-defined] # "TextIO" has no attribute "stream"
                reader = csv.DictReader(stream)
                if not set(CA_TRANSITIONS_CSV_HEADERS).issubset(set(reader.fieldnames)):  # type: ignore[arg-type] # Argument 1 to "set" has incompatible type "Optional[Sequence[str]]"; expected "Iterable[Any]"
                    error = f"{TransitionLogValidatorError.INVALID_CSV_HEADERS}: {set(reader.fieldnames)}"  # type: ignore[arg-type] # Argument 1 to "set" has incompatible type "Optional[Sequence[str]]"; expected "Iterable[str]"
                    log.info(error)
                    raise SubmittingTransitionLogErrors([error])

                for row in reader:
                    try:
                        member_id = int(row[CA_TRANSITIONS_CSV_HEADERS[0]])
                        old_cx_id = int(row[CA_TRANSITIONS_CSV_HEADERS[1]])
                        new_cx_id = int(row[CA_TRANSITIONS_CSV_HEADERS[2]])
                        messaging = row[CA_TRANSITIONS_CSV_HEADERS[3]].strip(" ;")

                        transitions.append([member_id, old_cx_id, new_cx_id, messaging])

                    except ValueError:
                        errors.append(
                            self._transition_error_str(
                                TransitionLogValidatorError.INVALID_CSV_DATA.value, row  # type: ignore[arg-type] # Argument 2 to "_transition_error_str" of "CareAdvocateMemberTransitionLogService" has incompatible type "Dict[Union[str, Any], Union[str, Any]]"; expected "List[Any]"
                            )
                        )
                        continue

        except UnicodeDecodeError:
            error = CareAdvocateMemberTransitionLogServiceMessage.NOT_IN_CSV_FORMAT
            log.info(error)
            raise SubmittingTransitionLogErrors([error])
        except AttributeError as ex:
            error = CareAdvocateMemberTransitionLogServiceMessage.FILE_ATTRIBUTE_ERROR
            log.info(error, exception=str(ex))
            raise SubmittingTransitionLogErrors([error])

        if not transitions and not errors:
            error = CareAdvocateMemberTransitionLogServiceMessage.NO_TRANSITIONS_FOUND
            log.info(error)
            raise SubmittingTransitionLogErrors([error])

        if errors:
            log.info(str(errors))
            raise SubmittingTransitionLogErrors(errors)

        return transitions

    @ddtrace.tracer.wrap()
    def submit_transition_log(
        self,
        user_id: int,
        transition_date: datetime,  # type: ignore[valid-type] # Module "datetime" is not valid as a type
        transitions_csv: TextIO,
    ) -> None:
        transitions_data = self._parse_transitions_data_from_csv(transitions_csv)

        with self.uow() as uow:
            transition_log = uow.get_repo(
                CareAdvocateMemberTransitionLogRepository
            ).create(
                instance=CareAdvocateMemberTransitionLog(
                    user_id=user_id,
                    date_scheduled=transition_date,
                    uploaded_filename=transitions_csv.filename,  # type: ignore[attr-defined] # "TextIO" has no attribute "filename"
                    uploaded_content=json.dumps(
                        self._convert_transitions_json(transitions_data)
                    ),
                )
            )
            uow.commit()
            emit_audit_log_create(transition_log)
            return transition_log


class TransitionLogError(Exception):
    ...


class IncorrectTransitionLogIDError(TransitionLogError):
    ...


class AlreadyCompletedTransitionError(TransitionLogError):
    ...


class DeletingTransitionLogError(TransitionLogError):
    ...


class SubmittingTransitionLogErrors(TransitionLogError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(self, str(errors))


class TransitionLogValidationError(Exception):
    ...


class TransitionLogValidatorError(str, enum.Enum):
    INVALID_CSV_HEADERS = "Invalid csv file, please check the file headers"
    INVALID_CSV_DATA = "Invalid data found in csv file"
    ALL_USERS_NOT_FOUND = "Could not find all users in file"
    MISSING_MEMBER_PROFILE = "Member record must have a member profile"
    INVALID_OLD_CX = "Old CX must be a care advocate"
    INVALID_NEW_CX = "New CX must be a care advocate"
    OLD_CX_NOT_ASSIGNED = "Old CX must be in the member's care team"
    NEW_CX_ALREADY_ASSIGNED = "New CX is already on the member's care team"
    MESSAGE_TYPE_UNKNOWN = "Unknown message type in csv file"
    DUPLICATE_MEMBER_FOUND = "Duplicate member found in the file"
    REASSIGN_EXCEPTION = "Could not reassign advocate due to unhandled exception"


class CareAdvocateMemberTransitionValidator:
    def __init__(self) -> None:
        self.message_templates = (
            CareAdvocateMemberTransitionTemplateService().get_message_templates_dict()
        )
        self.pending_member_ids = []

    def validate(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        member: User,
        old_cx: User,
        new_cx: User,
        message_types: list,
        row: list | None = None,
        record: dict | None = None,
    ):
        # Simplify logging record into row (list) for simplicity and consistancy
        if record:
            row = record.values()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "dict_values[Any, Any]", variable has type "Optional[List[Any]]")

        if None in (member, old_cx, new_cx):
            return self.ValidationError(
                TransitionLogValidatorError.ALL_USERS_NOT_FOUND, row  # type: ignore[arg-type] # Argument 2 to "ValidationError" has incompatible type "Optional[List[Any]]"; expected "List[Any]"
            )
        if message_types:
            for message_type in message_types:
                if message_type not in self.message_templates:
                    return self.ValidationError(
                        TransitionLogValidatorError.MESSAGE_TYPE_UNKNOWN, row  # type: ignore[arg-type] # Argument 2 to "ValidationError" has incompatible type "Optional[List[Any]]"; expected "List[Any]"
                    )
        if member.id in self.pending_member_ids:
            return self.ValidationError(
                TransitionLogValidatorError.DUPLICATE_MEMBER_FOUND, row  # type: ignore[arg-type] # Argument 2 to "ValidationError" has incompatible type "Optional[List[Any]]"; expected "List[Any]"
            )
        self.pending_member_ids.append(member.id)

        if not member.is_member:
            return self.ValidationError(
                TransitionLogValidatorError.MISSING_MEMBER_PROFILE, row  # type: ignore[arg-type] # Argument 2 to "ValidationError" has incompatible type "Optional[List[Any]]"; expected "List[Any]"
            )
        if not old_cx.is_care_coordinator:
            return self.ValidationError(TransitionLogValidatorError.INVALID_OLD_CX, row)  # type: ignore[arg-type] # Argument 2 to "ValidationError" has incompatible type "Optional[List[Any]]"; expected "List[Any]"
        if not new_cx.is_care_coordinator:
            return self.ValidationError(TransitionLogValidatorError.INVALID_NEW_CX, row)  # type: ignore[arg-type] # Argument 2 to "ValidationError" has incompatible type "Optional[List[Any]]"; expected "List[Any]"
        # Check new_cx before old_cx first so the response is more accurate (already transitioned)
        # We will consider these successes because they are assigned to the desired CA
        if new_cx in member.care_coordinators:
            log.info(TransitionLogValidatorError.NEW_CX_ALREADY_ASSIGNED, row=row)
            return self.ValidationError(
                CareAdvocateMemberTransitionResponse.SUCCESS, row  # type: ignore[arg-type] # Argument 1 to "ValidationError" has incompatible type "CareAdvocateMemberTransitionResponse"; expected "TransitionLogValidatorError" #type: ignore[arg-type] # Argument 2 to "ValidationError" has incompatible type "Optional[List[Any]]"; expected "List[Any]"
            )
        if old_cx not in member.care_coordinators:
            return self.ValidationError(
                TransitionLogValidatorError.OLD_CX_NOT_ASSIGNED, row  # type: ignore[arg-type] # Argument 2 to "ValidationError" has incompatible type "Optional[List[Any]]"; expected "List[Any]"
            )

    class ValidationError:
        def __init__(
            self,
            message: TransitionLogValidatorError,
            row: list,
        ):
            self.message_name = message.name
            self.message = message.value
            self.row = row

            log.error(
                "CA Member Transition Validation Issue",
                message=message,
                row=row,
            )
